import mlflow
from tests.make_synthetic_data import make
from src.data import build_universe, split_temporal, prepare
from src.train import run_one, threshold_for_recall


def test_universe_excludes_solo_danos():
    d = build_universe(make())
    assert set(d["fatal"].unique()) <= {0, 1}
    assert len(d) < len(make())


def test_split_is_temporal():
    tr, va, te = split_temporal(build_universe(make()))
    assert tr["anio"].max() <= 2023 and (va["anio"] == 2024).all() and (te["anio"] == 2025).all()


def test_run_logs_to_mlflow(tmp_path):
    p = tmp_path / "s.parquet"; make().to_parquet(p)
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/m.db"); mlflow.set_experiment("t")
    r = run_one(prepare(p), "hgb", "completo", {"data_md5": "x"})
    assert 0 <= r["val_pr_auc"] <= 1 and r["val_recall"] >= 0.7


def test_duplicates_removed_and_schema_mapped():
    raw = make()
    d = build_universe(raw)
    assert d.duplicated(["id_siniestro", "anio"]).sum() == 0
    assert {"clase", "elemento_choque", "fatal", "franja"} <= set(d.columns)


def test_posthoc_flags_informative_and_2025_unavailable():
    import numpy as np
    d = prepare_from_df()
    assert set(d.loc[d.anio <= 2024, "con_velocidad"].dropna().unique()) == {0.0, 1.0}
    assert d.loc[d.anio == 2025, "con_velocidad"].isna().all()
    assert d.loc[d.anio == 2025, "con_carga"].notna().all()


def prepare_from_df():
    import tempfile, os
    from src.data import prepare
    p = os.path.join(tempfile.mkdtemp(), "s.parquet"); make().to_parquet(p)
    return prepare(p)
