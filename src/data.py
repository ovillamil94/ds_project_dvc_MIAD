"""Carga y preparación de datos: universo, variable objetivo, split temporal y conjuntos de variables.

Universo: siniestros con víctimas (CON MUERTOS / CON HERIDOS).
Objetivo: fatal = 1 si el siniestro tiene muertos.
Los años del split y las listas de variables vienen de config.yml.
"""
from __future__ import annotations

import hashlib
import unicodedata

import numpy as np
import pandas as pd
from dateutil.easter import easter

from .config import load_config


def _norm(s: pd.Series) -> pd.Series:
    def f(x):
        if pd.isna(x):
            return np.nan
        x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
        return x.strip().upper()
    return s.map(f)


def file_md5(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _siguiente_lunes(ts: pd.Timestamp) -> pd.Timestamp:
    """Ley Emiliani: el festivo se traslada al lunes siguiente (si ya es lunes, se queda)."""
    return ts + pd.Timedelta(days=(7 - ts.weekday()) % 7)


def festivos_colombia(anios) -> pd.DatetimeIndex:
    """Festivos nacionales de Colombia (fijos, trasladables al lunes y los de Semana Santa)."""
    out = []
    for y in {int(a) for a in anios}:
        out += [pd.Timestamp(y, m, d) for m, d in [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]]
        out += [_siguiente_lunes(pd.Timestamp(y, m, d)) for m, d in [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]]
        pascua = pd.Timestamp(easter(y))
        out += [pascua - pd.Timedelta(days=3), pascua - pd.Timedelta(days=2)]  # jueves y viernes santo
        out += [_siguiente_lunes(pascua + pd.Timedelta(days=o)) for o in (39, 60, 68)]  # Ascensión, Corpus, Sagrado Corazón
    return pd.DatetimeIndex(sorted(set(out)))


RENAME = {"codigo_siniestro": "id_siniestro", "clase_nombre": "clase",
          "choque_nombre": "elemento_choque", "objeto_fijo_nombre": "objeto_fijo"}


def load_siniestros(path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    return df


def standardize(df: pd.DataFrame, source: str = "30d") -> pd.DataFrame:
    """Adapta el parquet consolidado al esquema de trabajo.

    - Renombra columnas (codigo_siniestro -> id_siniestro, clase_nombre -> clase, ...).
    - gravedad según `source`: "30d" (por defecto; cubre 2015-2025), "tradicional" (vacía en 2025)
      o "auto" (30d y, donde falte, la tradicional; mezcla definiciones, no recomendado).
    - Elimina siniestros repetidos entre archivos anuales (llave id_siniestro + anio), conservando el archivo más reciente.
    """
    d = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns and v not in df.columns}).copy()
    if "gravedad" not in d.columns:
        g30 = d["gravedad_30d_nombre"] if "gravedad_30d_nombre" in d.columns else pd.Series(np.nan, index=d.index)
        gtr = d["gravedad_tradicional_nombre"] if "gravedad_tradicional_nombre" in d.columns else pd.Series(np.nan, index=d.index)
        if source == "30d":
            d["gravedad"] = g30.astype("object")
        elif source == "tradicional":
            d["gravedad"] = gtr.astype("object")
        elif source == "auto":
            d["gravedad"] = g30.astype("object").where(g30.notna(), gtr.astype("object"))
        else:
            raise ValueError("source debe ser 30d, tradicional o auto")
    d["anio"] = pd.to_numeric(d["anio"], errors="coerce")
    d = d[d["anio"].notna()].copy()
    d["anio"] = d["anio"].astype(int)
    if "id_siniestro" in d.columns:
        if "source_year" in d.columns:
            d = d.sort_values("source_year", ascending=False, kind="stable")
        d = d.drop_duplicates(["id_siniestro", "anio"], keep="first")
    return d


def build_universe(df: pd.DataFrame, source: str = "30d") -> pd.DataFrame:
    """Filtra a siniestros con víctimas y crea objetivo y variables derivadas."""
    d = standardize(df, source)
    g = _norm(d["gravedad"]).astype("object")
    muertos = g.str.contains("MUERT", na=False)
    heridos = g.str.contains("HERID", na=False)
    d = d[muertos | heridos].copy()
    d["fatal"] = muertos.loc[d.index].astype(int)
    for c in ["localidad", "dia_semana", "clase", "elemento_choque", "objeto_fijo"]:
        if c in d:
            d[c] = _norm(d[c]).astype("object").fillna("DESCONOCIDO")
    d["hora"] = pd.to_numeric(d["hora"], errors="coerce")
    d = d[d["hora"].between(0, 23).fillna(False).astype(bool)].copy()
    d["hora"] = d["hora"].astype(int)
    d["mes"] = pd.to_numeric(d["mes"], errors="coerce").fillna(0).astype(int)
    d["es_fin_semana"] = d["dia_semana"].isin(["SABADO", "DOMINGO"]).astype(int)
    d["es_madrugada"] = d["hora"].isin([0, 1, 2, 3, 4, 5]).astype(int)
    d["franja"] = pd.cut(d["hora"], [-1, 5, 11, 17, 23], labels=["MADRUGADA", "MANANA", "TARDE", "NOCHE"]).astype(str)
    for c in ["latitud", "longitud"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")  # faltantes: los imputa el pipeline
    d = _add_v2_features(d)
    return d.reset_index(drop=True)


def _add_v2_features(d: pd.DataFrame) -> pd.DataFrame:
    """Variables derivadas de la versión 2. Todas se conocen al recibir la llamada.
    Solo entran al modelo si config.yml las incluye en un grupo de variables."""
    h = d["hora"].astype(float)
    d["hora_sin"] = np.sin(2 * np.pi * h / 24)  # la hora es cíclica: las 23 y las 0 están cerca
    d["hora_cos"] = np.cos(2 * np.pi * h / 24)
    fecha = pd.to_datetime(d["fecha"], errors="coerce") if "fecha" in d.columns else pd.Series(pd.NaT, index=d.index)
    if fecha.notna().any():
        fest = festivos_colombia(range(int(fecha.dt.year.min()), int(fecha.dt.year.max()) + 1))
        d["es_festivo"] = fecha.dt.normalize().isin(fest).astype(int)
    else:
        d["es_festivo"] = 0
    d["es_quincena"] = fecha.dt.day.isin([1, 14, 15, 16, 29, 30, 31]).astype(int)  # días de pago
    d["localidad_franja"] = d["localidad"].astype(str) + "_" + d["franja"].astype(str)
    ok = d["latitud"].notna() & d["longitud"].notna()
    celda = d["latitud"].round(2).astype(str) + "_" + d["longitud"].round(2).astype(str)  # ~1 km
    d["celda_geo"] = np.where(ok, celda, "SIN_COORD")
    return d


def split_temporal(d: pd.DataFrame, cfg: dict | None = None):
    s = (cfg or load_config())["split"]
    tr = d[d["anio"] <= s["train_max"]]
    va = d[d["anio"] == s["val_year"]]
    te = d[d["anio"] == s["test_year"]]
    return tr, va, te


def features_for(name: str, d: pd.DataFrame, cfg: dict | None = None):
    """Devuelve (cat_cols, num_cols) para un conjunto de variables definido en config.yml.

    Los grupos cuyo nombre empieza por 'cat_' son categóricos; los demás, numéricos.
    Solo se conservan columnas que existen en `d`.
    """
    cfg = cfg or load_config()
    cat, num = [], []
    for g in cfg["feature_sets"][name]:
        cols = [c for c in cfg["features"][g] if c in d.columns]
        (cat if g.startswith("cat_") else num).extend(cols)
    return cat, num


def flag_columns(cfg: dict, d: pd.DataFrame | None = None) -> list[str]:
    """Banderas con_* usadas por cualquier grupo de variables de config.yml (el consolidado solo las registra cuando son verdaderas)."""
    cols = []
    for group in cfg["features"].values():
        cols += [c for c in group if c.startswith("con_") and c not in cols]
    return [c for c in cols if d is None or c in d.columns]


def prepare(path, source: str = "30d", cfg: dict | None = None):
    cfg = cfg or load_config()
    raw = load_siniestros(path)
    d = build_universe(raw, source)
    for c in flag_columns(cfg, d):
        d[c] = pd.to_numeric(d[c].astype("float"), errors="coerce")
        # El consolidado solo registra la bandera cuando es verdadera (blanco = no hay factor).
        # Si un año no trae NINGÚN dato de la bandera (p. ej. 2025), no existe: se deja NaN en vez de 0.
        hay = d.groupby("anio")[c].transform(lambda x: x.notna().any())
        d[c] = d[c].where(~hay, d[c].fillna(0))
    return d


def posthoc_coverage(d: pd.DataFrame, year: int, cfg: dict | None = None, cols: list[str] | None = None) -> float:
    """Proporción de banderas que existen en un año (1 = todas; 0 = ninguna). `cols` por defecto: grupo 'posthoc'."""
    cfg = cfg or load_config()
    cols = [c for c in (cols if cols is not None else cfg["features"]["posthoc"]) if c in d.columns]
    sub = d[d["anio"] == year]
    if not cols or not len(sub):
        return 0.0
    return float(np.mean([sub[c].notna().any() for c in cols]))
