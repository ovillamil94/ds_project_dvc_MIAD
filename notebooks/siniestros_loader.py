"""
siniestros_loader.py
====================
Load and standardise the three data tabs of the Bogotá road-crash workbooks
(Base_Anuario_de_Siniestralidad_Vial_<year>.xlsx, 2019-2025):

    siniestros  one row per crash
    vehiculos   one row per vehicle involved in a crash
    actor_vial  one row per person (driver, passenger, pedestrian...) involved

Quick start
-----------
    import siniestros_loader as sl

    # all three tabs -> three parquet files
    tablas = sl.build_all(RAW, interim_dir=INTERIM, out_dir=OUT_DIR)

    # or one tab at a time (the tab name is a parameter)
    df = sl.build_table_by_name(RAW, "vehiculos", interim_dir=INTERIM, out_path=OUT_DIR / "vehiculos.parquet")

Sheet names are matched ignoring case, accents and space/underscore, so
"vehiculos" finds 'VEHICULOS', 'Vehiculos' and 'Vehículos'; "actor_vial" finds
'Actor vial'.  An integer is treated as a sheet position.

Join keys:  siniestros.codigo_siniestro  <-  vehiculos.codigo_siniestro
            vehiculos (codigo_siniestro, codigo_vehiculo) <- actor_vial (same two)

Requires: pandas, openpyxl, pyarrow.
"""
from __future__ import annotations

import re
import unicodedata
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd


# =========================================================================== #
# 1. Small helpers
# =========================================================================== #
def _fold(text: str) -> str:
    """Remove accents: 'Vehículo' -> 'Vehiculo'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _key(name) -> str:
    """Normalised lookup key: 'Actor vial' -> 'actor_vial', 'CLASE_' -> 'clase'."""
    return re.sub(r"[^a-z0-9]+", "_", _fold(str(name)).lower()).strip("_")


def extract_year(path: Path) -> int:
    """Last 4-digit year found in the file name."""
    years = re.findall(r"(?:19|20)\d{2}", Path(path).stem)
    if not years:
        raise ValueError(f"No year found in file name: {Path(path).name}")
    return int(years[-1])


# =========================================================================== #
# 2. Column casting
# =========================================================================== #
_PD_DTYPE = {"int64": "Int64", "int32": "Int32", "int16": "Int16", "text": "string",
             "text_raw": "string", "bool": "boolean", "float": "float64",
             "date": "datetime64[ns]", "datetime": "datetime64[ns]"}

_BOOL_MAP = {**{k: True for k in ("SI", "S", "1", "1.0", "TRUE", "VERDADERO")},
             **{k: False for k in ("NO", "N", "0", "0.0", "FALSE", "FALSO")}}

DIAS = {0: "LUNES", 1: "MARTES", 2: "MIERCOLES", 3: "JUEVES", 4: "VIERNES", 5: "SABADO", 6: "DOMINGO"}


def _clean_text(s: pd.Series, fold_upper: bool) -> pd.Series:
    """Trim; collapse spaces; optionally remove accents and upper-case."""
    s = s.astype("string")
    mapping = {}
    for v in s.dropna().unique():
        t = re.sub(r"\s+", " ", str(v)).strip()
        mapping[v] = _fold(t).upper() if fold_upper else t
    return s.map(mapping).astype("string")


def _to_float(s: pd.Series) -> pd.Series:
    """Handles decimal commas ('-74,1366') as well as normal floats."""
    if s.dtype == object or str(s.dtype) in ("string", "str"):
        s = s.astype("string").str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").astype("float64")


def _cast(s: pd.Series, kind: str) -> pd.Series:
    if kind in ("int64", "int32", "int16"):
        return pd.to_numeric(s, errors="coerce").round().astype(_PD_DTYPE[kind])
    if kind == "float":
        return _to_float(s)
    if kind == "date":
        return pd.to_datetime(s, errors="coerce").dt.normalize().astype("datetime64[ns]")
    if kind == "text":
        return _clean_text(s, fold_upper=True)
    if kind == "text_raw":
        return _clean_text(s, fold_upper=False)
    if kind == "bool":   # SI/NO, S/N, 1/0
        return _clean_text(s, fold_upper=True).map(_BOOL_MAP).astype("boolean")
    raise ValueError(kind)


def _empty(kind: str, index: pd.Index) -> pd.Series:
    if kind in ("date", "datetime"):
        return pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")
    if kind == "float":
        return pd.Series(np.nan, index=index, dtype="float64")
    return pd.Series(pd.NA, index=index, dtype=_PD_DTYPE[kind])


def _move_numeric_names_to_codes(df: pd.DataFrame, bases: list[str]) -> pd.DataFrame:
    """If a <base>_nombre column holds only numbers, it is really a code column.
    (e.g. 2020-21 'CLASE' = 01, 02... while 2023+ 'Clase' = 'Bus', 'Motocicleta')"""
    for base in bases:
        nom, cod = f"{base}_nombre", f"{base}_codigo"
        if nom not in df:
            continue
        s = df[nom].dropna()
        if len(s) and pd.to_numeric(s, errors="coerce").notna().all():
            df[cod] = df[cod].combine_first(df[nom]) if cod in df else df[nom]
            df = df.drop(columns=[nom])
    return df


# =========================================================================== #
# 3. Table specifications
# =========================================================================== #
# Every CON_* flag seen in any year/tab. A year that does not publish a flag
# gets <NA> (= "not reported", NOT "NO").
CON_FLAGS = [
    "bicicleta", "carga", "embriaguez", "huecos", "menores", "moto", "peaton",
    "persona_mayor", "rutas", "tpi", "tpp", "velocidad", "sitp", "transmilenio",
    "troncal", "alimentador", "zonal", "provisional", "articulado",
    "biarticulado", "padron_dual", "servicio_especial", "taxi",
]


def _con(extra: Iterable[str] = ()) -> dict[str, str]:
    return {f"con_{f}": "bool" for f in [*extra, *CON_FLAGS]}


@dataclass
class TableSpec:
    name: str
    sheet: str                       # default sheet name to look for
    column_map: dict                 # normalised source name -> standard name
    schema: dict                     # standard name -> kind (order = output order)
    derived_source: set              # source columns dropped and recomputed from `fecha`
    code_bases: list = field(default_factory=list)   # <base>_codigo / <base>_nombre pairs
    prefer: list = field(default_factory=list)       # [(keep_key, drop_key)] when both exist
    value_fixes: dict = field(default_factory=dict)  # {std_col: {OLD: NEW}} after upper/accents
    key_cols: list = field(default_factory=list)     # duplicate check
    check_cols: list = field(default_factory=list)   # null-% check


DERIVED = {"fecha_hora", "anio", "mes", "dia", "dia_semana"}

# ----- SINIESTROS ----------------------------------------------------------- #
SINIESTROS = TableSpec(
    name="siniestros", sheet="siniestros",
    column_map={
        "accidente": "codigo_siniestro", "codigo_accidente": "codigo_siniestro",
        "codigo_siniestro": "codigo_siniestro",
        "formulario": "formulario",
        "fecha": "fecha", "fechaacc": "fecha", "fecha_acc": "fecha", "fecha_siniestro": "fecha",
        "hora": "hora", "houracc": "hora", "hora_acc": "hora", "hora_siniestro": "hora",
        "minuto": "minuto", "minuacc": "minuto", "min_acc": "minuto", "min_siniestro": "minuto",
        "direccion": "direccion",
        "codigo_localidad": "localidad_codigo", "localidad": "localidad",
        "diseno_lugar": "diseno_lugar_codigo",
        "longitud": "longitud", "latitud": "latitud",
        "clasecodigo": "clase_codigo", "clase": "clase_codigo",
        "clasenombre": "clase_nombre", "clase_acc": "clase_nombre", "clase_siniestro": "clase_nombre",
        "choque": "choque_codigo",
        "choquenombre": "choque_nombre", "elemento_choque": "choque_nombre",
        "objeto_fijo": "objeto_fijo_codigo",
        "objetofijonombre": "objeto_fijo_nombre", "tipo_objeto_fijo": "objeto_fijo_nombre",
        "gravedad": "gravedad_tradicional_codigo",
        "gravedadnombre": "gravedad_tradicional_nombre",   # 2020-21 hold codes -> auto-moved
        "gravedad_indicador_tradicional": "gravedad_tradicional_nombre",
        "gravedad30": "gravedad_30d_codigo",
        "gravedadnombre30": "gravedad_30d_nombre", "gravedad_indicador_30d": "gravedad_30d_nombre",
    },
    schema={
        "codigo_siniestro": "int64", "formulario": "text",
        "fecha": "date", "hora": "int16", "minuto": "int16",
        "fecha_hora": "datetime", "anio": "int16", "mes": "int16", "dia": "int16", "dia_semana": "text",
        "direccion": "text_raw", "localidad_codigo": "int16", "localidad": "text",
        "diseno_lugar_codigo": "int16", "longitud": "float", "latitud": "float",
        "clase_codigo": "int16", "clase_nombre": "text",
        "choque_codigo": "int16", "choque_nombre": "text",
        "objeto_fijo_codigo": "int16", "objeto_fijo_nombre": "text",
        "gravedad_tradicional_codigo": "int16", "gravedad_tradicional_nombre": "text",
        "gravedad_30d_codigo": "int16", "gravedad_30d_nombre": "text",
        **_con(),
    },
    derived_source={"annoacc", "mesacc", "dayacc", "wdyacc", "aa_acc", "mm_acc", "dd_mes_acc",
                    "dia_semana_acc", "aa_siniestro", "mm_siniestro", "dd_mes_siniestro",
                    "dia_semana_siniestro"},
    code_bases=["clase", "choque", "objeto_fijo", "gravedad_tradicional", "gravedad_30d"],
    prefer=[("fechaacc", "fecha")],   # 2022 has FECHA (date+time) and FechaAcc: keep FechaAcc
    key_cols=["codigo_siniestro", "formulario"],
    check_cols=["codigo_siniestro", "fecha", "hora", "localidad", "longitud", "latitud",
                "clase_nombre", "gravedad_tradicional_nombre", "gravedad_30d_nombre"],
)

# ----- VEHICULOS ------------------------------------------------------------ #
# NOTE: in 2020-21 CLASE / SERVICIO / MODALIDAD are numeric codes, in the other
# years they are names. Both are mapped to <base>_nombre and the numeric ones
# are moved to <base>_codigo automatically (see _move_numeric_names_to_codes).
VEHICULOS = TableSpec(
    name="vehiculos", sheet="vehiculos",
    column_map={
        "accidente": "codigo_siniestro", "codigo_accidente": "codigo_siniestro",
        "codigo_siniestro": "codigo_siniestro",
        "vehiculo": "codigo_vehiculo", "codigo_vehiculo": "codigo_vehiculo",
        "formulario": "formulario",
        "fechaacc": "fecha", "fecha_acc": "fecha", "fecha_siniestro": "fecha",
        "clasevehiculo": "clase_vehiculo_nombre", "clase": "clase_vehiculo_nombre",
        "serviciovehiculo": "servicio_nombre", "servicio": "servicio_nombre",
        "modalidadvehiculo": "modalidad_nombre", "modalidad": "modalidad_nombre",
        "vehiculoenfuga": "en_fuga", "enfuga": "en_fuga",
        "vehiculo_viajaba_clasificado": "vehiculo_clasificado",
        "tipo_sitp": "tipo_sitp",
    },
    schema={
        "codigo_siniestro": "int64", "codigo_vehiculo": "int16", "formulario": "text",
        "fecha": "date", "anio": "int16",
        "clase_vehiculo_codigo": "int16", "clase_vehiculo_nombre": "text",
        "servicio_codigo": "int16", "servicio_nombre": "text",
        "modalidad_codigo": "int16", "modalidad_nombre": "text",
        "en_fuga": "bool", "vehiculo_clasificado": "text", "tipo_sitp": "text",
        **_con(),
    },
    derived_source={"annoacc", "aa_acc", "aa_siniestro"},
    code_bases=["clase_vehiculo", "servicio", "modalidad"],
    key_cols=["codigo_siniestro", "codigo_vehiculo"],
    check_cols=["codigo_siniestro", "formulario", "fecha", "clase_vehiculo_nombre",
                "servicio_nombre", "modalidad_nombre", "en_fuga", "vehiculo_clasificado"],
)

# ----- ACTOR_VIAL ----------------------------------------------------------- #
ACTOR_VIAL = TableSpec(
    name="actor_vial", sheet="actor_vial",
    column_map={
        "accidente": "codigo_siniestro", "codigo_accidente": "codigo_siniestro",
        "codigo_siniestro": "codigo_siniestro",
        "codigo_accidentado": "codigo_accidentado",
        "vehiculo": "codigo_vehiculo", "codigo_vehiculo": "codigo_vehiculo",
        "codigo_victima": "codigo_victima", "ccodigo_victima": "codigo_victima",   # (sic, 'Ccodigo')
        "formulario": "formulario",
        "fecha": "fecha", "fechaacc": "fecha", "fechasiniestro": "fecha",
        "hora": "hora", "houracc": "hora", "hoursiniestro": "hora",
        "minuto": "minuto", "minuacc": "minuto", "minusiniestro": "minuto",
        "localidad": "localidad",
        "edad": "edad",
        "sexo": "sexo", "genero_actv": "sexo",
        "gravedad_procesada": "gravedad_tradicional",
        "gravedad_procesada_actv": "gravedad_tradicional",
        "gravedad_indicador_tradicional": "gravedad_tradicional",
        "gravedad_procesada30": "gravedad_30d", "gravedad_indicador_30d": "gravedad_30d",
        "muerte_posterior": "muerte_posterior",
        "fecha_cambiogravedad": "fecha_cambio_gravedad",
        "clinica_atencion": "clinica_atencion",
        "condicion": "condicion",            # 2022: 'CONDICION_' (trailing _ is ignored)
        "condicion_actv": "condicion_actv",  # 2022 only, kept separate
        "condicion_especifica": "condicion_especifica",
        "tipo_sitp": "tipo_sitp",
        "victimac": "victima_categoria", "asociadoc": "asociado_categoria",   # 2025 only
    },
    schema={
        "codigo_siniestro": "int64", "codigo_accidentado": "int64",
        "codigo_vehiculo": "int16", "codigo_victima": "int16", "formulario": "text",
        "fecha": "date", "hora": "int16", "minuto": "int16",
        "fecha_hora": "datetime", "anio": "int16", "mes": "int16", "dia": "int16", "dia_semana": "text",
        "localidad": "text", "edad": "int16", "sexo": "text",
        "gravedad_tradicional": "text", "gravedad_30d": "text",
        "muerte_posterior": "bool", "fecha_cambio_gravedad": "date", "clinica_atencion": "int32",
        "condicion": "text", "condicion_actv": "text", "condicion_especifica": "text",
        "tipo_sitp": "text", "victima_categoria": "text", "asociado_categoria": "text",
        **_con(extra=["cinturon", "casco"]),
    },
    derived_source={"annoacc", "mesacc", "dayacc", "wdyacc", "dd_mes_acc", "dia_semana_acc",
                    "annosiniestro", "messiniestro", "dd_mes_siniestro", "dia_semana_siniestro"},
    value_fixes={"gravedad_tradicional": {"ILESA": "ILESO"}, "gravedad_30d": {"ILESA": "ILESO"}},
    key_cols=["codigo_accidentado"],
    check_cols=["codigo_siniestro", "codigo_accidentado", "fecha", "edad", "sexo",
                "gravedad_tradicional", "gravedad_30d", "condicion", "condicion_especifica"],
)

SPECS = {s.name: s for s in (SINIESTROS, VEHICULOS, ACTOR_VIAL)}


# =========================================================================== #
# 4. Standardise one yearly dataframe
# =========================================================================== #
def standardize(raw: pd.DataFrame, year: int, source_file: str, spec: TableSpec) -> pd.DataFrame:
    keys = {c: _key(c) for c in raw.columns}
    for keep, drop in spec.prefer:
        if keep in keys.values():
            keys = {c: k for c, k in keys.items() if k != drop}
    df = raw[list(keys)]

    rename, drop_cols, unknown = {}, [], []
    for col, k in keys.items():
        if k in spec.column_map:
            rename[col] = spec.column_map[k]
        elif k.startswith("con_"):
            rename[col] = k
        elif k in spec.derived_source:
            drop_cols.append(col)
        else:
            rename[col] = k
            unknown.append(k)
    df = df.drop(columns=drop_cols).rename(columns=rename)

    dup = df.columns[df.columns.duplicated()].unique().tolist()
    if dup:
        raise ValueError(f"[{spec.name}] {year}: several source columns map to the same name: {dup}")
    if unknown:
        warnings.warn(f"[{spec.name}] {year}: columns not in the column map were kept as-is: {unknown}")

    df = _move_numeric_names_to_codes(df, spec.code_bases)

    out = {}
    for name, kind in spec.schema.items():
        if name in DERIVED:
            continue
        out[name] = _cast(df[name], kind) if name in df else _empty(kind, df.index)
    for c in df.columns:                      # new CON_* flags / unmapped columns are carried along
        if c not in spec.schema:
            out[c] = _cast(df[c], "bool") if c.startswith("con_") else df[c]
    for col, fixes in spec.value_fixes.items():
        if col in out:
            out[col] = out[col].replace(fixes)
    res = pd.DataFrame(out, index=df.index)

    # derived columns: same definition for every year
    sch = spec.schema
    if "fecha_hora" in sch:
        h, m = res["hora"].astype("float64"), res["minuto"].astype("float64")
        res["fecha_hora"] = (res["fecha"] + pd.to_timedelta(h.fillna(0), unit="h")
                             + pd.to_timedelta(m.fillna(0), unit="m")
                             ).where(res["fecha"].notna() & h.notna()).astype("datetime64[ns]")
    if "anio" in sch:
        res["anio"] = res["fecha"].dt.year.astype("Int16")
    if "mes" in sch:
        res["mes"] = res["fecha"].dt.month.astype("Int16")
    if "dia" in sch:
        res["dia"] = res["fecha"].dt.day.astype("Int16")
    if "dia_semana" in sch:
        res["dia_semana"] = res["fecha"].dt.dayofweek.map(DIAS).astype("string")

    res.insert(0, "source_year", np.int16(year))
    res.insert(1, "source_file", source_file)
    extras = [c for c in res.columns if c not in sch and c not in ("source_year", "source_file")]
    return res[["source_year", "source_file", *sch, *extras]]


def standardize_siniestros(raw, year, source_file=""):
    return standardize(raw, year, source_file, SINIESTROS)


def standardize_vehiculos(raw, year, source_file=""):
    return standardize(raw, year, source_file, VEHICULOS)


def standardize_actor_vial(raw, year, source_file=""):
    return standardize(raw, year, source_file, ACTOR_VIAL)


# =========================================================================== #
# 5. Code <-> name filling (after all years are stacked)
#    1) learns code->name pairs from rows that have both (e.g. siniestros 2022)
#    2) applies `manual_maps` (values you copy from the DICCIONARIO sheet)
#    3) fills the other years and REPORTS whatever is still unresolved.
# =========================================================================== #
def fill_code_name_pairs(df: pd.DataFrame, bases: list[str],
                         manual_maps: dict[str, dict] | None = None,
                         verbose: bool = True) -> pd.DataFrame:
    """manual_maps example: {"servicio": {1: "PARTICULAR", 2: "PUBLICO"}}  (names upper-case, no accents)"""
    df = df.copy()
    manual_maps = manual_maps or {}
    for base in bases:
        cod, nom = f"{base}_codigo", f"{base}_nombre"
        pairs = df[[cod, nom]].dropna().drop_duplicates()
        c2n = pairs.drop_duplicates(cod, keep=False).set_index(cod)[nom].to_dict()
        n2c = pairs.drop_duplicates(nom, keep=False).set_index(nom)[cod].to_dict()
        for k, v in manual_maps.get(base, {}).items():
            c2n[k] = v
            n2c[v] = k
        df[nom] = df[nom].fillna(df[cod].map(c2n).astype("string"))
        df[cod] = df[cod].fillna(pd.to_numeric(df[nom].map(n2c), errors="coerce").astype("Int16"))
        if verbose:
            print(f"[{base}] code->name known: { {int(k): v for k, v in c2n.items()} }")
            no_name = df.loc[df[cod].notna() & df[nom].isna(), ["source_year", cod]].drop_duplicates()
            if len(no_name):
                miss = {int(c): sorted(g["source_year"].astype(int).tolist())
                        for c, g in no_name.groupby(cod)}
                print(f"    codes with NO name yet (code: years) -> look them up in DICCIONARIO: {miss}")
            no_code = sorted(df.loc[df[nom].notna() & df[cod].isna(), nom].unique().tolist())
            if no_code:
                print(f"    names with NO code yet: {no_code[:15]}{' ...' if len(no_code) > 15 else ''}")
    return df


# =========================================================================== #
# 6. Reading workbooks
# =========================================================================== #
def list_workbooks(raw_dir: Path, pattern: str = "*.xlsx") -> list[Path]:
    files = sorted(p for p in Path(raw_dir).glob(pattern) if not p.name.startswith("~$"))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern} in {raw_dir}. Did you run `dvc pull`?")
    return files


def resolve_sheet(sheet_names: list[str], sheet: str | int) -> str:
    """Find the real sheet name ignoring case, accents and space/underscore."""
    if isinstance(sheet, int):
        return sheet_names[sheet]
    k = _key(sheet)
    for n in sheet_names:
        if _key(n) == k:
            return n
    raise ValueError(f"Sheet '{sheet}' not found. Available: {sheet_names}")


def load_sheet(path: Path, sheet: str | int = "siniestros", header: int = 0, **read_kw) -> pd.DataFrame:
    """Read one tab of one workbook (raw, no cleaning)."""
    with pd.ExcelFile(path) as xls:
        name = resolve_sheet(xls.sheet_names, sheet)
        df = xls.parse(name, header=header, **read_kw)
    print(f"  {Path(path).name}: sheet '{name}' -> {df.shape[0]:,} rows x {df.shape[1]} cols")
    return df


# =========================================================================== #
# 7. Build the combined tables
# =========================================================================== #
def build_table(
    raw_dir: Path,
    sheet: str | int,
    standardize_fn: Callable[[pd.DataFrame, int, str], pd.DataFrame],
    post_fn: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    interim_dir: Path | None = None,
    out_path: Path | None = None,
    years: Iterable[int] | None = None,
    force: bool = False,
    header: int = 0,
) -> pd.DataFrame:
    """
    Read `sheet` from every workbook, standardise each year, stack them and
    (optionally) write a parquet file.

    interim_dir : each standardised year is cached there as parquet so re-runs
                  skip the slow Excel read. Use force=True after changing a spec.
    """
    years = set(years) if years else None
    frames = []
    for f in list_workbooks(raw_dir):
        year = extract_year(f)
        if years and year not in years:
            continue
        cache = Path(interim_dir) / f"{_key(sheet)}_{year}.parquet" if interim_dir else None
        if cache is not None and cache.exists() and not force:
            print(f"  {f.name}: using cache {cache.name}")
            frames.append(pd.read_parquet(cache))
            continue
        raw = load_sheet(f, sheet=sheet, header=header)
        std = standardize_fn(raw, year, f.name)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            std.to_parquet(cache, index=False)
        frames.append(std)
        del raw

    df = pd.concat(frames, ignore_index=True)
    if post_fn is not None:
        df = post_fn(df)
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, index=False)
        print(f"Saved {len(df):,} rows x {df.shape[1]} cols -> {out_path}")
    return df


def build_table_by_name(raw_dir: Path, table: str, sheet: str | int | None = None,
                        manual_maps: dict | None = None, **kw) -> pd.DataFrame:
    """table = 'siniestros' | 'vehiculos' | 'actor_vial'.  `sheet` defaults to the table name."""
    spec = SPECS[table]
    return build_table(
        raw_dir, sheet if sheet is not None else spec.sheet,
        standardize_fn=lambda raw, year, fname: standardize(raw, year, fname, spec),
        post_fn=(lambda d: fill_code_name_pairs(d, spec.code_bases, manual_maps)) if spec.code_bases else None,
        **kw,
    )


def build_siniestros(raw_dir, sheet="siniestros", **kw):
    return build_table_by_name(raw_dir, "siniestros", sheet, **kw)


def build_vehiculos(raw_dir, sheet="vehiculos", **kw):
    return build_table_by_name(raw_dir, "vehiculos", sheet, **kw)


def build_actor_vial(raw_dir, sheet="actor_vial", **kw):
    return build_table_by_name(raw_dir, "actor_vial", sheet, **kw)


def build_all(raw_dir: Path, interim_dir: Path | None = None, out_dir: Path | None = None,
              tables: Iterable[str] = ("siniestros", "vehiculos", "actor_vial"),
              manual_maps: dict[str, dict] | None = None, force: bool = False) -> dict[str, pd.DataFrame]:
    """Build every table; writes <out_dir>/<table>.parquet. Returns {table: DataFrame}."""
    result = {}
    for t in tables:
        print(f"\n=== {t} ===")
        result[t] = build_table_by_name(
            raw_dir, t, manual_maps=manual_maps, interim_dir=interim_dir, force=force,
            out_path=(Path(out_dir) / f"{t}.parquet") if out_dir else None)
    return result


# =========================================================================== #
# 8. Quick checks to run after a build
# =========================================================================== #
def quick_checks(df: pd.DataFrame, table: str = "siniestros") -> None:
    spec = SPECS[table]
    print(f"\n[{table}] rows per source file year:")
    print(df.groupby("source_year").size().to_string())
    if "anio" in df and df["anio"].notna().any():
        print("\nEvent year (from fecha) vs file year  -> files may contain older events:")
        print(pd.crosstab(df["anio"], df["source_year"], dropna=False).to_string())
    keyed = df.dropna(subset=spec.key_cols)   # rows without the key (e.g. no codigo_accidentado in 2019) are not duplicates
    print(f"\nDuplicated ({', '.join(spec.key_cols)}): {keyed.duplicated(spec.key_cols).sum():,}"
          f"  | rows without that key: {len(df) - len(keyed):,}")
    cols = [c for c in spec.check_cols if c in df]
    print("\n% null per source year (selected columns):")
    print(df.groupby("source_year")[cols].apply(lambda g: g.isna().mean() * 100).round(1).to_string())
