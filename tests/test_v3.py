import mlflow
from src.config import load_config
from src.data import flag_columns, prepare
from src.train import run_one
from tests.make_synthetic_data import make


def test_v3_flags_filled_only_where_year_has_data(tmp_path):
    cfg = load_config("configs/v3.yml")
    assert "con_carga" in flag_columns(cfg)
    p = tmp_path / "s.parquet"; make().to_parquet(p)
    d = prepare(p, cfg=cfg)
    assert set(d.loc[d.anio <= 2025, "con_carga"].dropna().unique()) == {0.0, 1.0}
    assert d.loc[d.anio == 2025, "con_carga"].notna().all()


def test_v3_run_logs_full_coverage_and_beats_nothing_silently(tmp_path):
    cfg = load_config("configs/v3.yml")
    p = tmp_path / "s.parquet"; make().to_parquet(p)
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/m.db"); mlflow.set_experiment("v3t")
    r = run_one(prepare(p, cfg=cfg), {"model": "hgb", "features": "evento_carga"}, {"data_md5": "x"}, cfg=cfg)
    run = mlflow.search_runs(experiment_names=["v3t"]).iloc[0]
    assert run["tags.version_modelo"] == "v3"
    assert run["metrics.cobertura_posthoc_test"] == 1.0 and run["metrics.cobertura_posthoc_val"] == 1.0
    assert "con_carga" in run["params.features"]
