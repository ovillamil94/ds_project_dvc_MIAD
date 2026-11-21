"""Exporta el modelo registrado en MLflow a la carpeta model/ (se hornea dentro de la imagen Docker).

Uso (en su computador, con el venv del proyecto activo):
    python export_model.py --tracking-uri sqlite:///C:/ruta/ds_project_dvc_MIAD/mlflow.db
    python export_model.py --tracking-uri http://<IP_EC2>:8050 --model-name fatalidad_llamada --alias champion
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracking-uri", default="sqlite:///mlflow.db")
    ap.add_argument("--model-name", default="fatalidad_llamada", help="fatalidad_llamada (despacho) o fatalidad_escena")
    ap.add_argument("--alias", default="champion", help="champion, modelo_v1, modelo_v2...")
    ap.add_argument("--out", default="model")
    a = ap.parse_args()

    mlflow.set_tracking_uri(a.tracking_uri)
    client = MlflowClient()
    mv = client.get_model_version_by_alias(a.model_name, a.alias)
    run = client.get_run(mv.run_id)
    p, t, m = run.data.params, run.data.tags, run.data.metrics

    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    with tempfile.TemporaryDirectory() as tmp:
        local = mlflow.artifacts.download_artifacts(artifact_uri=f"models:/{a.model_name}@{a.alias}", dst_path=tmp)
        shutil.copytree(local, out)

    meta = {
        "model_name": a.model_name, "alias": a.alias, "model_version": mv.version,
        "run_name": t.get("mlflow.runName"), "version_modelo": t.get("version_modelo"),
        "feature_set": p.get("feature_set"), "features": [c for c in p.get("features", "").split(",") if c],
        "threshold": float(p["threshold"]) if "threshold" in p else None,
        "recall_target": float(p["recall_target"]) if "recall_target" in p else None,
        "val_pr_auc": m.get("val_pr_auc"), "test_pr_auc": m.get("test_pr_auc"),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Ejemplo de solicitud para probar la API (a partir del input_example que guardo train.py)
    try:
        ex = json.loads((out / "input_example.json").read_text(encoding="utf-8"))
        ex = ex.get("dataframe_split", ex)
        records = [dict(zip(ex["columns"], row)) for row in ex["data"][:2]]
        (out / "example_request.json").write_text(json.dumps({"records": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print("No se pudo crear example_request.json:", exc)

    py = next((l.split(":")[1].strip() for l in (out / "MLmodel").read_text().splitlines() if "python_version" in l), "?")
    print(f"Modelo {a.model_name}@{a.alias} (version {mv.version}) exportado a {out}/")
    print(f"Variables ({len(meta['features'])}): {meta['features']}")
    print(f"Umbral: {meta['threshold']}")
    print(f"Python con el que se entreno: {py}  ->  docker build --build-arg PYTHON_VERSION={'.'.join(py.split('.')[:2])} ...")


if __name__ == "__main__":
    main()
