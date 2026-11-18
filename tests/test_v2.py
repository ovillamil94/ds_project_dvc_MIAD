import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from src import register
from src.config import load_config
from src.data import build_universe, features_for, festivos_colombia, prepare
from src.train import run_one
from tests.make_synthetic_data import make


def test_festivos_colombia_2024():
    esperados = pd.to_datetime(["2024-01-01", "2024-01-08", "2024-03-25", "2024-03-28", "2024-03-29", "2024-05-01",
                                "2024-05-13", "2024-06-03", "2024-06-10", "2024-07-01", "2024-07-20", "2024-08-07",
                                "2024-08-19", "2024-10-14", "2024-11-04", "2024-11-11", "2024-12-08", "2024-12-25"])
    got = festivos_colombia([2024])
    assert set(esperados) == set(got)


def test_new_features_created():
    d = build_universe(make())
    for c in ["hora_sin", "hora_cos", "es_festivo", "es_quincena", "localidad_franja", "celda_geo"]:
        assert c in d.columns and d[c].notna().all()
    assert (d["celda_geo"] == "SIN_COORD").any() and d["es_festivo"].isin([0, 1]).all()


def test_v2_config_and_run(tmp_path):
    cfg = load_config("configs/v2.yml")
    assert cfg["experiment"]["version"] == "v2" and len(cfg["experiments"]) >= 10
    p = tmp_path / "s.parquet"; make().to_parquet(p)
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/m.db"); mlflow.set_experiment("v2t")
    d = prepare(p, cfg=cfg)
    r = run_one(d, {"model": "hgb", "features": "evento_v2"}, {"data_md5": "x"}, cfg=cfg)
    assert r["val_pr_auc_ci_low"] <= r["val_pr_auc"] <= r["val_pr_auc_ci_high"]
    assert 0 < r["val_brier"] < 0.2
    run = mlflow.search_runs(experiment_names=["v2t"]).iloc[0]
    assert run["tags.version_modelo"] == "v2"
    cat1, num1 = features_for("evento", d, load_config())
    assert int(run["params.n_features"]) > len(cat1) + len(num1)


def test_register_creates_versions_with_aliases(tmp_path, monkeypatch):
    p = tmp_path / "s.parquet"; make().to_parquet(p)
    uri = f"sqlite:///{tmp_path}/r.db"
    mlflow.set_tracking_uri(uri)
    cfg1, cfg2 = load_config(), load_config("configs/v2.yml")
    for cfg, exp, spec in [(cfg1, "fatalidad_siniestros_bogota", {"model": "hgb", "features": "evento"}),
                           (cfg2, "fatalidad_siniestros_bogota_v2", {"model": "hgb", "features": "evento_v2"})]:
        mlflow.set_experiment(exp)
        run_one(prepare(p, cfg=cfg), spec, {"data_md5": "x"}, cfg=cfg)
    for exp, run in [("fatalidad_siniestros_bogota", "hgb__evento"), ("fatalidad_siniestros_bogota_v2", "hgb__evento_v2")]:
        monkeypatch.setattr("sys.argv", ["register", "--tracking-uri", uri, "--experiment", exp,
                                         "--llamada-run", run, "--escena-run", run])
        register.main()
    c = MlflowClient()
    assert c.get_model_version_by_alias("fatalidad_llamada", "modelo_v1").version in (1, "1")
    assert c.get_model_version_by_alias("fatalidad_llamada", "champion").version in (2, "2")


def test_register_solo_escena(tmp_path, monkeypatch):
    p = tmp_path / "s.parquet"; make().to_parquet(p)
    uri = f"sqlite:///{tmp_path}/r2.db"
    mlflow.set_tracking_uri(uri); mlflow.set_experiment("fatalidad_siniestros_bogota")
    run_one(prepare(p), {"model": "hgb", "features": "evento"}, {"data_md5": "x"})
    monkeypatch.setattr("sys.argv", ["register", "--tracking-uri", uri, "--escena-run", "hgb__evento", "--solo", "escena"])
    register.main()
    c = MlflowClient()
    assert c.get_registered_model("fatalidad_escena") is not None
    names = [m.name for m in c.search_registered_models()]
    assert "fatalidad_llamada" not in names
