"""API de predicción de fatalidad de siniestros viales (Bogotá).

Recibe lo que se conoce al momento de la llamada y devuelve la probabilidad de que el
siniestro tenga muertos, y si supera el umbral de alerta (elegido en validación).
Las variables derivadas (franja, fin de semana, madrugada) se calculan aquí igual que en src/data.py.
"""
from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

log = logging.getLogger("uvicorn.error")
MODEL_DIR = Path(__file__).resolve().parent / "model"

pipe = joblib.load(MODEL_DIR / "model.joblib")
meta = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
CAT, NUM = meta["cat_cols"], meta["num_cols"]
COLS = CAT + NUM
THR = float(meta["threshold"])
if meta["sklearn_version"] != sklearn.__version__:
    log.warning("scikit-learn del modelo (%s) != instalado (%s): fije la versión en requirements.txt",
                meta["sklearn_version"], sklearn.__version__)


def norm(x) -> str | None:
    """Misma normalización que data._norm: sin tildes, mayúsculas, sin espacios."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
    return x.strip().upper()


def franja(h: int) -> str:
    return "MADRUGADA" if h <= 5 else "MANANA" if h <= 11 else "TARDE" if h <= 17 else "NOCHE"


class Siniestro(BaseModel):
    localidad: str = Field(..., examples=["KENNEDY"])
    dia_semana: str = Field(..., examples=["SABADO"])
    hora: int = Field(..., ge=0, le=23, examples=[2])
    mes: int = Field(..., ge=1, le=12, examples=[11])
    latitud: float | None = Field(None, examples=[4.63])
    longitud: float | None = Field(None, examples=[-74.15])
    # Solo se usan si el modelo se exportó con el conjunto 'evento'
    clase: str | None = None
    elemento_choque: str | None = None
    objeto_fijo: str | None = None


class Prediccion(BaseModel):
    probabilidad_fatal: float
    alerta: bool
    umbral: float


def to_frame(items: list[Siniestro]) -> pd.DataFrame:
    rows = []
    for s in items:
        dia = norm(s.dia_semana)
        rows.append({
            "localidad": norm(s.localidad), "dia_semana": dia, "franja": franja(s.hora),
            "hora": s.hora, "mes": s.mes,
            "latitud": np.nan if s.latitud is None else s.latitud,
            "longitud": np.nan if s.longitud is None else s.longitud,
            "es_fin_semana": int(dia in ("SABADO", "DOMINGO")), "es_madrugada": int(s.hora <= 5),
            "clase": norm(s.clase) or "DESCONOCIDO",
            "elemento_choque": norm(s.elemento_choque) or "DESCONOCIDO",
            "objeto_fijo": norm(s.objeto_fijo) or "DESCONOCIDO",
        })
    df = pd.DataFrame(rows)[COLS]
    for c in NUM:
        df[c] = df[c].astype(float)
    return df


def score(items: list[Siniestro]) -> list[Prediccion]:
    df = to_frame(items)
    for c in CAT:  # categorías no vistas en entrenamiento: el modelo las ignora, pero avisamos
        unk = set(df[c].dropna()) - set(meta["known_categories"][c])
        if unk:
            log.warning("Categoría desconocida en %s: %s", c, sorted(unk))
    p = pipe.predict_proba(df)[:, 1]
    return [Prediccion(probabilidad_fatal=round(float(x), 5), alerta=bool(x >= THR), umbral=THR) for x in p]


app = FastAPI(title="Fatalidad de siniestros viales - Bogotá", version="1.0")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info():
    return {k: v for k, v in meta.items() if k != "known_categories"} | {
        "localidades_conocidas": meta["known_categories"].get("localidad", [])}


@app.post("/predict", response_model=Prediccion)
def predict(s: Siniestro):
    r = score([s])[0]
    log.info("predict localidad=%s hora=%s -> p=%.4f alerta=%s", s.localidad, s.hora, r.probabilidad_fatal, r.alerta)
    return r


@app.post("/predict_batch", response_model=list[Prediccion])
def predict_batch(items: list[Siniestro]):
    if not 0 < len(items) <= 1000:
        raise HTTPException(422, "Envíe entre 1 y 1000 siniestros")
    return score(items)
