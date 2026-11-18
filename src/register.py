"""Registra en el Model Registry de MLflow los modelos elegidos y les asigna el alias 'champion'.

Uso (después de entrenar):
    python -m src.register
Cada ejecución crea una NUEVA versión del modelo registrado (v1, v2, ...), con las métricas como etiquetas.
"""
from __future__ import annotations

import argparse

import mlflow
from mlflow.tracking import MlflowClient

# Nombre de la corrida elegida (tags.mlflow.runName) por defecto; se puede cambiar con --llamada-run / --escena-run
DEFAULT_LLAMADA, DEFAULT_ESCENA = "hgb__evento", "hgb__completo"
DESCRIPTIONS = {
    "fatalidad_llamada": "Modelo para el despacho: hora, lugar y tipo de siniestro.",
    "fatalidad_escena": "Modelo con factores registrados en la escena (carga, velocidad, embriaguez, persona mayor).",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracking-uri", default="sqlite:///mlflow.db")
    ap.add_argument("--experiment", default="fatalidad_siniestros_bogota")
    ap.add_argument("--llamada-run", default=DEFAULT_LLAMADA, help="nombre de la corrida para fatalidad_llamada")
    ap.add_argument("--escena-run", default=DEFAULT_ESCENA, help="nombre de la corrida para fatalidad_escena")
    ap.add_argument("--version-label", default=None, help="v1 / v2; por defecto se lee de la etiqueta version_modelo de la corrida "
                                                          "(las corridas v1 entrenadas antes de esta versión no la tienen: use --version-label v1)")
    ap.add_argument("--solo", choices=["llamada", "escena"], default=None,
                    help="registrar solo uno de los dos modelos (p. ej. --solo escena para subir una versión nueva solo de fatalidad_escena)")
    ap.add_argument("--no-champion", action="store_true", help="registrar la versión sin moverle el alias champion")
    a = ap.parse_args()
    targets = [(a.llamada_run, "fatalidad_llamada"), (a.escena_run, "fatalidad_escena")]
    if a.solo:
        targets = [t for t in targets if t[1] == f"fatalidad_{a.solo}"]
    mlflow.set_tracking_uri(a.tracking_uri)
    client = MlflowClient()
    exp = client.get_experiment_by_name(a.experiment)
    if exp is None:
        raise SystemExit(f"No existe el experimento {a.experiment}. Entrene primero con src.train --all")
    for run_name, model_name in targets:
        desc = DESCRIPTIONS[model_name]
        runs = client.search_runs([exp.experiment_id], filter_string=f"tags.mlflow.runName = '{run_name}'",
                                  order_by=["attributes.start_time DESC"], max_results=1)
        if not runs:
            raise SystemExit(f"No hay ninguna corrida llamada '{run_name}'. Revise los nombres en MLflow y use --llamada-run / --escena-run.")
        run = runs[0]
        mv = mlflow.register_model(f"runs:/{run.info.run_id}/model", model_name)
        client.update_registered_model(model_name, description=desc)
        vtag = a.version_label or run.data.tags.get("version_modelo", "")
        if vtag:  # alias modelo_v1 / modelo_v2 (MLflow reserva 'v1', 'v2'): models:/fatalidad_llamada@modelo_v1 funciona aunque champion apunte a otra versión
            client.set_registered_model_alias(model_name, f"modelo_{vtag}", mv.version)
        if not a.no_champion:
            client.set_registered_model_alias(model_name, "champion", mv.version)
        client.set_model_version_tag(model_name, mv.version, "version_modelo", vtag)
        for k in ("val_pr_auc", "val_pr_auc_ci_low", "val_pr_auc_ci_high", "val_recall", "val_precision", "val_alert_rate", "val_brier"):
            if k in run.data.metrics:
                client.set_model_version_tag(model_name, mv.version, k, f"{run.data.metrics[k]:.4f}")
        client.set_model_version_tag(model_name, mv.version, "run_name", run_name)
        client.set_model_version_tag(model_name, mv.version, "gravedad_fuente", run.data.tags.get("gravedad_fuente", ""))
        print(f"{model_name} v{mv.version} <- {run_name} (version_modelo={vtag or '-'}, champion={'no' if a.no_champion else 'si'})")


if __name__ == "__main__":
    main()
