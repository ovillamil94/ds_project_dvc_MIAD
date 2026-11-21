"""API de fatalidad de siniestros viales en Bogota.

Carga el modelo exportado (model/) y expone:
    GET  /            -> redirige a /docs (Swagger)
    GET  /health      -> estado del servicio
    GET  /info        -> version del modelo, umbral y variables requeridas
    POST /predict     -> probabilidad de siniestro fatal + alerta segun el umbral
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fatalidad-api")

# En el contenedor: /app/model. Se puede cambiar con MODEL_DIR (o MODEL_URI para cargar desde MLflow).
MODEL_DIR = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parent.parent / "model"))
MODEL_URI = os.getenv("MODEL_URI")  # opcional, ej. models:/fatalidad_llamada@champion (requiere MLFLOW_TRACKING_URI)

STATE: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = MODEL_URI or str(MODEL_DIR)
    log.info("Cargando modelo desde %s", source)
    STATE["pipe"] = mlflow.sklearn.load_model(source)
    meta_path = MODEL_DIR / "meta.json"
    STATE["meta"] = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    STATE["features"] = STATE["meta"].get("features") or list(
        getattr(STATE["pipe"], "feature_names_in_", [])
    )
    log.info("Modelo listo. Variables: %s | umbral: %s", STATE["features"], STATE["meta"].get("threshold"))
    yield
    STATE.clear()


app = FastAPI(
    title="API de fatalidad de siniestros - Bogotá",
    description="Predice la probabilidad de que un siniestro con víctimas tenga muertos (fatal = 1).",
    version=str(os.getenv("API_VERSION", "1.0")),
    lifespan=lifespan,
)


class PredictRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(
        ..., min_length=1, max_length=1000,
        description="Lista de siniestros; cada uno con todas las variables de GET /info",
    )


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": "pipe" in STATE}


@app.get("/info")
def info():
    m = STATE["meta"]
    return {
        "model_name": m.get("model_name"),
        "model_version": m.get("model_version"),
        "run_name": m.get("run_name"),
        "version_modelo": m.get("version_modelo"),
        "feature_set": m.get("feature_set"),
        "threshold": m.get("threshold"),
        "recall_target": m.get("recall_target"),
        "required_features": STATE["features"],
    }


@app.post("/predict")
def predict(req: PredictRequest):
    feats = STATE["features"]
    df = pd.DataFrame(req.records)
    missing = [c for c in feats if c not in df.columns]
    if missing:
        raise HTTPException(status_code=422, detail={"faltan_variables": missing, "requeridas": feats})
    df = df[feats]
    try:
        proba = STATE["pipe"].predict_proba(df)[:, 1]
    except Exception as exc:  # tipos incorrectos, etc.
        log.exception("Error al predecir")
        raise HTTPException(status_code=422, detail=f"No se pudo predecir: {exc}")
    thr = STATE["meta"].get("threshold")
    preds = [
        {"probabilidad_fatal": round(float(p), 5),
         "alerta": (bool(p >= thr) if thr is not None else None)}
        for p in proba
    ]
    log.info("predict: %d registro(s), alertas=%d", len(preds), sum(bool(x["alerta"]) for x in preds))
    return {"umbral": thr, "model_version": STATE["meta"].get("model_version"), "predicciones": preds}
