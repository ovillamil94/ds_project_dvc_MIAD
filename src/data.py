"""Carga y preparación de datos: universo, variable objetivo, split temporal y conjuntos de variables.

Universo: siniestros con víctimas (CON MUERTOS / CON HERIDOS).
Objetivo: fatal = 1 si el siniestro tiene muertos.
Split temporal: train <= 2023, validación 2024, test 2025.
"""
from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

TRAIN_MAX, VAL_YEAR, TEST_YEAR = 2023, 2024, 2025

# Variables conocidas al recibir la llamada / al llegar al lugar
CAT_LLAMADA = ["localidad", "dia_semana", "franja"]
NUM_LLAMADA = ["hora", "mes", "latitud", "longitud", "es_fin_semana", "es_madrugada"]
CAT_EVENTO = ["clase", "elemento_choque", "objeto_fijo"]
# Banderas CON_* que SÍ existen en 2025 (se detectan en tiempo de ejecución) y las post-hoc (solo <=2024)
POSTHOC = ["con_velocidad", "con_embriaguez", "con_persona_mayor", "con_carga"]

FEATURE_SETS = {
    "llamada": (CAT_LLAMADA, NUM_LLAMADA),
    "evento": (CAT_LLAMADA + CAT_EVENTO, NUM_LLAMADA),
    "completo": (CAT_LLAMADA + CAT_EVENTO, NUM_LLAMADA),  # + banderas, ver features_for()
}


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


RENAME = {"codigo_siniestro": "id_siniestro", "clase_nombre": "clase",
          "choque_nombre": "elemento_choque", "objeto_fijo_nombre": "objeto_fijo"}


def load_siniestros(path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    return df


def standardize(df: pd.DataFrame, source: str = "30d") -> pd.DataFrame:
    """Adapta el parquet consolidado al esquema de trabajo.

    - Renombra columnas (codigo_siniestro -> id_siniestro, clase_nombre -> clase, ...).
    - gravedad según `source`: "30d" (por defecto; es la definición de la exploración, 5.489 muertos y cubre 2015-2025),
      "tradicional" (vacía en 2025) o "auto" (30d y, donde falte, la tradicional; mezcla definiciones, no recomendado).
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
    return d.reset_index(drop=True)


def split_temporal(d: pd.DataFrame):
    tr = d[d["anio"] <= TRAIN_MAX]
    va = d[d["anio"] == VAL_YEAR]
    te = d[d["anio"] == TEST_YEAR]
    return tr, va, te


def features_for(name: str, d: pd.DataFrame):
    """Devuelve (cat_cols, num_cols) para un conjunto de variables, solo con columnas existentes."""
    cat, num = FEATURE_SETS[name]
    if name == "completo":
        num = num + [c for c in POSTHOC if c in d.columns]
    cat = [c for c in cat if c in d.columns]
    num = [c for c in num if c in d.columns]
    return cat, num


def prepare(path, source: str = "30d"):
    raw = load_siniestros(path)
    d = build_universe(raw, source)
    for c in POSTHOC:
        if c in d:
            d[c] = pd.to_numeric(d[c].astype("float"), errors="coerce")
            # El consolidado solo registra la bandera cuando es verdadera (blanco = no hay factor).
            # Si un año no trae NINGÚN dato de la bandera (p. ej. 2025), no existe: se deja NaN en vez de 0.
            hay = d.groupby("anio")[c].transform(lambda x: x.notna().any())
            d[c] = d[c].where(~hay, d[c].fillna(0))
    return d


def posthoc_coverage(d: pd.DataFrame, year: int) -> float:
    """Proporción de banderas post-hoc que existen en un año (1 = todas; 0 = ninguna). Si es < 1, ese año no es comparable en 'completo'."""
    cols = [c for c in POSTHOC if c in d.columns]
    sub = d[d["anio"] == year]
    if not cols or not len(sub):
        return 0.0
    return float(np.mean([sub[c].notna().any() for c in cols]))
