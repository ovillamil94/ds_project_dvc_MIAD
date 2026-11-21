"""Carga resultados_v*.csv en MLflow: una corrida (run) por fila de cada CSV.

Reglas para decidir que es cada columna (se imprimen antes de registrar):
  - columna de nombre : la primera columna de texto cuyo nombre contiene modelo/model/nombre/name/...
                        (o la que se indique con --name-col). Se usa como nombre de la corrida.
  - parametro         : columnas de texto, booleanas, hiperparametros conocidos (max_depth,
                        n_estimators, threshold...) y las indicadas con --param-cols.
  - metrica           : cualquier otra columna numerica (recall, precision, pr_auc, f1...).

Cada CSV es una "version" (resultados_v1 -> tag version_modelo=resultados_v1). Si se ejecuta de
nuevo, las corridas de esa version se reemplazan (no se duplican).

Uso:
    python log_results_to_mlflow.py --dry-run                      # solo muestra la clasificacion
    python log_results_to_mlflow.py --tracking-uri http://localhost:8050
    python log_results_to_mlflow.py --param-cols max_depth,cv --name-col modelo
    python log_results_to_mlflow.py --sep ";" --decimal ","        # CSV exportado desde Excel en espanol
"""
import argparse
import glob
import os
import re
import unicodedata

import pandas as pd

HYPERPARAMS = re.compile(
    r"^(max_depth|max_leaf_nodes|min_samples_\w+|min_weight_\w+|n_estimators|learning_rate|max_iter|"
    r"max_features|criterion|splitter|ccp_alpha|class_weight|random_state|seed|threshold|umbral|"
    r"recall_target|feature_set|n_features|cv|k|profundidad\w*|semilla|criterio|umbral\w*)$",
    re.I,
)
NAME_HINTS = ("modelo", "model", "nombre", "name", "algoritmo", "algorithm", "experimento", "experiment", "run")


def clean(name):
    """MLflow solo admite letras, numeros, _ - . espacio y /. Quita tildes y reemplaza el resto."""
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    out = re.sub(r"[^A-Za-z0-9_\-\. /]", "_", ascii_name)
    return re.sub(r"_+", "_", out).strip("_ ") or "col"


def classify(df, name_col, param_cols):
    """Devuelve (name_col, params, metrics) como listas de nombres de columna."""
    forced = {c.strip() for c in param_cols if c.strip()}
    unknown = [c for c in forced if c not in df.columns]
    if unknown:
        raise SystemExit(f"--param-cols contiene columnas que no existen: {unknown}. Columnas: {list(df.columns)}")
    if name_col and name_col not in df.columns:
        raise SystemExit(f"--name-col '{name_col}' no existe. Columnas: {list(df.columns)}")

    if not name_col:
        for c in df.columns:
            if not pd.api.types.is_numeric_dtype(df[c]) and any(h in c.lower() for h in NAME_HINTS):
                name_col = c
                break

    params, metrics = [], []
    for c in df.columns:
        if c == name_col:
            continue
        is_num = pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
        norm = clean(c).lower().replace(" ", "_")
        if c in forced or HYPERPARAMS.match(norm) or not is_num:
            params.append(c)
        else:
            metrics.append(c)
    return name_col, params, metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracking-uri", default="http://localhost:8050")
    ap.add_argument("--experiment", default="validacion_arboles")
    ap.add_argument("--pattern", default="resultados_v*.csv")
    ap.add_argument("--name-col", default=None, help="columna con el nombre del modelo (por defecto se detecta)")
    ap.add_argument("--param-cols", default="", help="columnas a forzar como parametros, separadas por coma")
    ap.add_argument("--sep", default=None, help="separador del CSV (por defecto se detecta)")
    ap.add_argument("--decimal", default=".", help="separador decimal del CSV (use ',' si viene de Excel en espanol)")
    ap.add_argument("--dry-run", action="store_true", help="solo muestra la clasificacion, no registra nada")
    a = ap.parse_args()

    files = sorted(glob.glob(a.pattern))
    if not files:
        raise SystemExit(f"No hay archivos que coincidan con '{a.pattern}' en {os.getcwd()}")

    if not a.dry_run:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(a.tracking_uri)
        mlflow.set_experiment(a.experiment)
        client = MlflowClient()
        exp_id = mlflow.get_experiment_by_name(a.experiment).experiment_id

    total = 0
    for path in files:
        version = os.path.splitext(os.path.basename(path))[0]  # resultados_v1
        df = pd.read_csv(path, sep=a.sep, engine="python", decimal=a.decimal)
        df.columns = [str(c).strip() for c in df.columns]
        name_col, params, metrics = classify(df, a.name_col, a.param_cols.split(","))

        print(f"\n{path}: {len(df)} filas, {len(df.columns)} columnas")
        print(f"  nombre de corrida : {name_col or '(ninguna: se usa fila0, fila1, ...)'}")
        print(f"  parametros        : {params}")
        print(f"  metricas          : {metrics}")
        if not metrics:
            print("  AVISO: no hay columnas numericas para usar como metricas. Revise --param-cols / --sep / --decimal.")
        if a.dry_run:
            continue

        # Reemplazar las corridas previas de esta version (evita duplicados al re-ejecutar)
        old = client.search_runs([exp_id], filter_string=f"tags.version_modelo = '{version}'", max_results=1000)
        for r in old:
            client.delete_run(r.info.run_id)
        if old:
            print(f"  (se reemplazaron {len(old)} corridas anteriores de {version})")

        for i, row in df.iterrows():
            label = str(row[name_col]) if name_col and pd.notna(row[name_col]) else f"fila{i}"
            with mlflow.start_run(run_name=f"{version}__{label}"):
                mlflow.set_tag("version_modelo", version)
                mlflow.set_tag("fuente_csv", os.path.basename(path))
                for c in params:
                    if pd.notna(row[c]):
                        mlflow.log_param(clean(c), str(row[c])[:500])
                for c in metrics:
                    if pd.notna(row[c]):
                        mlflow.log_metric(clean(c), float(row[c]))
                mlflow.log_artifact(path)
        total += len(df)
        print(f"  {len(df)} corridas registradas")

    if a.dry_run:
        print("\nDry-run: no se registro nada.")
    else:
        print(f"\nListo: {total} corridas en el experimento '{a.experiment}' ({a.tracking_uri})")


if __name__ == "__main__":
    main()
