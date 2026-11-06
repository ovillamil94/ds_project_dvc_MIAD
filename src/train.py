"""Experimentos de modelado con MLflow, parametrizados con config.yml.

Uso:
    python -m src.train --data data/processed/siniestros.parquet --all
    python -m src.train --data ... --all --config configs/variante.yml --experiment fatalidad_variante
    python -m src.train --data ... --model hgb --features evento          # una sola corrida
    mlflow ui --backend-store-uri sqlite:///mlflow.db
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import DEFAULT_CONFIG, load_config
from .data import features_for, file_md5, posthoc_coverage, prepare, split_temporal


def make_pipeline(model_name: str, cat, num, cfg: dict, overrides: dict | None = None):
    """Construye el pipeline. Los hiperparámetros vienen de cfg['models'][model_name],
    y `overrides` (params de la corrida en config.yml) tiene prioridad."""
    mf = cfg["preprocessing"]["min_frequency"]
    seed = cfg["experiment"]["seed"]
    hp = {**cfg["models"][model_name], **(overrides or {})}
    if model_name == "logreg":
        pre = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=mf), cat),
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
        ])
        clf = LogisticRegression(**hp)
    else:
        pre = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=mf, sparse_output=False), cat),
            ("num", SimpleImputer(strategy="median"), num),
        ])
        clf = HistGradientBoostingClassifier(**{"random_state": seed, **hp})
    return Pipeline([("pre", pre), ("clf", clf)])


def threshold_for_recall(y, p, target=0.80):
    """Mayor umbral que logra recall >= target en validación (menos falsas alarmas)."""
    prec, rec, thr = precision_recall_curve(y, p)
    ok = np.where(rec[:-1] >= target)[0]
    return float(thr[ok[-1]]) if len(ok) else float(thr[0])


def recall_at_top(y, p, frac):
    k = max(1, int(round(len(y) * frac)))
    idx = np.argsort(-p)[:k]
    return float(np.asarray(y)[idx].sum() / max(1, np.asarray(y).sum()))


def metrics_at(y, p, thr, prefix):
    y = np.asarray(y)
    pred = (p >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {
        f"{prefix}_pr_auc": float(average_precision_score(y, p)),
        f"{prefix}_roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan"),
        f"{prefix}_recall": tp / max(1, tp + fn),
        f"{prefix}_precision": tp / max(1, tp + fp),
        f"{prefix}_alert_rate": float(pred.mean()),
        f"{prefix}_recall_top10": recall_at_top(y, p, 0.10),
        f"{prefix}_recall_top20": recall_at_top(y, p, 0.20),
        f"{prefix}_prevalence": float(y.mean()),
    }


class PriorBaseline:
    """Línea base 1: la prevalencia de entrenamiento para todos."""
    def __init__(self, y): self.p = float(np.mean(y))
    def predict_proba1(self, X): return np.full(len(X), self.p)


class RateTableBaseline:
    """Línea base 2: letalidad histórica suavizada por franja x localidad."""
    def __init__(self, tr, y, k=20):
        self.prior = float(np.mean(y)); self.k = k
        g = tr.assign(_y=np.asarray(y)).groupby(["franja", "localidad"])["_y"].agg(["sum", "count"])
        self.tab = ((g["sum"] + k * self.prior) / (g["count"] + k)).to_dict()
    def predict_proba1(self, X):
        return np.array([self.tab.get((f, l), self.prior) for f, l in zip(X["franja"], X["localidad"])])


def log_importance(pipe, X, y, cat, num, seed):
    r = permutation_importance(pipe, X, y, scoring="average_precision", n_repeats=5, random_state=seed, n_jobs=1)
    imp = pd.Series(r.importances_mean, index=cat + num).sort_values()
    fig, ax = plt.subplots(figsize=(6, max(3, 0.3 * len(imp))))
    imp.plot.barh(ax=ax); ax.set_xlabel("Caída de PR-AUC al permutar (validación)")
    fig.tight_layout()
    with tempfile.TemporaryDirectory() as t:
        fig.savefig(f"{t}/permutation_importance.png", dpi=120)
        mlflow.log_artifact(f"{t}/permutation_importance.png")
        imp.to_csv(f"{t}/permutation_importance.csv")
        mlflow.log_artifact(f"{t}/permutation_importance.csv")
    plt.close(fig)


def run_one(d, spec: dict, data_tag: dict, register: bool = False, cfg: dict | None = None):
    """Ejecuta una corrida. spec = {"model": ..., "features": ..., "name": opcional, "params": opcional}."""
    cfg = cfg or load_config()
    e, s = cfg["experiment"], cfg["split"]
    model_name, fset = spec["model"], spec["features"]
    run_name = spec.get("name") or f"{model_name}__{fset}"
    overrides = spec.get("params") or {}

    tr, va, te = split_temporal(d, cfg)
    if min(len(tr), len(va), len(te)) == 0 or tr["fatal"].sum() == 0:
        raise ValueError("Split vacío o sin positivos: revise los años en config.yml (split) y los datos.")
    cat, num = features_for(fset, d, cfg)
    cols = cat + num
    with mlflow.start_run(run_name=run_name):
        mlflow.set_tags({"modelo": model_name, "conjunto_variables": fset, **data_tag})
        mlflow.log_params({"model": model_name, "feature_set": fset, "n_features": len(cols),
                           "features": ",".join(cols), "train_hasta": s["train_max"], "val": s["val_year"],
                           "test": s["test_year"], "recall_target": e["recall_target"], "seed": e["seed"],
                           "min_frequency": cfg["preprocessing"]["min_frequency"],
                           "n_train": len(tr), "n_val": len(va), "n_test": len(te)})
        mlflow.log_dict({"run_name": run_name, "spec": spec, "config": cfg}, "config_resolved.yaml")
        if model_name == "baseline_prior":
            m = PriorBaseline(tr["fatal"]); pv, pt = m.predict_proba1(va), m.predict_proba1(te); pipe = None
        elif model_name == "baseline_tabla":
            m = RateTableBaseline(tr, tr["fatal"], k=cfg["baselines"]["rate_table_k"])
            pv, pt = m.predict_proba1(va), m.predict_proba1(te); pipe = None
            mlflow.log_param("rate_table_k", cfg["baselines"]["rate_table_k"])
        else:
            pipe = make_pipeline(model_name, cat, num, cfg, overrides)
            pipe.fit(tr[cols], tr["fatal"])
            mlflow.log_params({f"clf__{k}": v for k, v in pipe.named_steps["clf"].get_params().items()})
            pv, pt = pipe.predict_proba(va[cols])[:, 1], pipe.predict_proba(te[cols])[:, 1]
        thr = threshold_for_recall(va["fatal"], pv, e["recall_target"]) if np.ptp(pv) > 0 else 0.5  # puntaje constante (baseline_prior): nunca alerta
        mlflow.log_param("threshold", round(thr, 5))
        if "posthoc" in cfg["feature_sets"][fset]:  # si es ~0, las banderas no existen en ese año y el resultado no es comparable
            mlflow.log_metrics({"cobertura_posthoc_val": posthoc_coverage(d, s["val_year"], cfg),
                                "cobertura_posthoc_test": posthoc_coverage(d, s["test_year"], cfg)})
        mets = {**metrics_at(va["fatal"], pv, thr, "val"), **metrics_at(te["fatal"], pt, thr, "test")}
        mlflow.log_metrics({k: v for k, v in mets.items() if not np.isnan(v)})
        if pipe is not None:
            log_importance(pipe, va[cols], va["fatal"], cat, num, e["seed"])
            sig = infer_signature(va[cols].head(200), pv[:200])
            mlflow.sklearn.log_model(pipe, name="model", signature=sig, serialization_format="cloudpickle",
                                     input_example=va[cols].head(3),
                                     registered_model_name=f"fatalidad_{fset}" if register else None)
        return {"run": run_name, **{k: round(v, 4) for k, v in mets.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="ruta a un config.yml alternativo")
    ap.add_argument("--data", required=True)
    ap.add_argument("--tracking-uri", default=None, help="por defecto, experiment.tracking_uri del yml")
    ap.add_argument("--experiment", default=None, help="por defecto, experiment.name del yml")
    ap.add_argument("--model", default="hgb"); ap.add_argument("--features", default="llamada")
    ap.add_argument("--gravedad-source", default=None, choices=["30d", "tradicional", "auto"])
    ap.add_argument("--all", action="store_true", help="ejecuta la lista 'experiments' del yml")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    cfg = load_config(a.config)
    e = cfg["experiment"]
    tracking_uri = a.tracking_uri or e["tracking_uri"]
    experiment = a.experiment or e["name"]
    gsource = a.gravedad_source or e["gravedad_source"]
    out = a.out or e["output_csv"]

    mlflow.set_tracking_uri(tracking_uri); mlflow.set_experiment(experiment)
    d = prepare(a.data, gsource, cfg)
    tag = {"gravedad_fuente": gsource, "data_md5": file_md5(a.data), "data_file": Path(a.data).name,
           "n_universo": str(len(d)), "config_file": str(Path(a.config or DEFAULT_CONFIG).name)}
    todo = cfg["experiments"] if a.all else [{"model": a.model, "features": a.features}]
    rows = [run_one(d, spec, tag, a.register, cfg) for spec in todo]
    res = pd.DataFrame(rows); res.to_csv(out, index=False)
    print(res[["run", "val_pr_auc", "val_recall", "val_precision", "test_pr_auc", "test_recall", "test_precision"]].to_string(index=False))


if __name__ == "__main__":
    main()
