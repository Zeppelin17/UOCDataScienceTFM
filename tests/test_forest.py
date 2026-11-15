"""Bosque acotado, aislamiento temporal y sección del notebook sin reajustar logística."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.data import read_result, save_result
from tfm.forest import (FOREST_PARAMETERS, CANDIDATE_COLUMNS, RESULT_NAMES, _classifier,
                        fit_forest_partition, run_forest)
from tfm.walk_forward import (build_walk_forward_splits, build_interaction_feature,
                              INTERACTION_COLUMN, SIGNAL_COLUMNS)
from test_logistic import fixture_samples, PARAMETERS


def forest_inputs():
    features, _, samples = fixture_samples()
    interaction = build_interaction_feature(features)
    samples = samples.merge(interaction[["target_period", INTERACTION_COLUMN]], on="target_period", validate="many_to_one")
    pieces = []
    for (split, year), calendar in build_walk_forward_splits().groupby(["split_id", "test_year"], sort=True):
        for rule in ("momentum", "reversal"):
            rows = samples.loc[samples.sample_usable & samples.strategy.eq(rule)].merge(
                calendar[["target_period", "role"]], on="target_period", validate="one_to_one")
            p = rows.loc[rows.role.eq("validation"), ["target_period", "label"]].reset_index(drop=True)
            p.insert(0, "strategy", rule); p.insert(0, "test_year", int(year)); p.insert(0, "split_id", int(split))
            p["probability_naive"] = float(rows.loc[rows.role.eq("train"), "label"].mean())
            p["probability_logistic"] = .51
            p["probability_regime"] = .52
            pieces.append(p)
    return samples, pd.concat(pieces, ignore_index=True), PARAMETERS.copy(), {"attempt": "m2", "reference_attempt": "m1"}


def test_fixed_forest_does_not_use_validation_labels_and_respects_purge():
    samples, _, _, _ = forest_inputs()
    cal = build_walk_forward_splits().loc[lambda t: t.test_year.eq(1950)]
    rows = samples.loc[samples.sample_usable & samples.strategy.eq("momentum")].merge(
        cal[["target_period", "role"]], on="target_period", validate="one_to_one")
    train, test = rows.loc[rows.role.eq("train")].copy(), rows.loc[rows.role.eq("validation")].copy()
    p, d = fit_forest_partition(train, test, strategy="momentum", split_id=1, year=1950, columns=SIGNAL_COLUMNS)
    changed = test.copy(); changed["label"] = 1-changed.label
    changed["z_credit_spread_pp"] = 1e10
    train["z_credit_spread_pp"] = -1e10
    p2, d2 = fit_forest_partition(train, changed, strategy="momentum", split_id=1, year=1950, columns=SIGNAL_COLUMNS)
    pd.testing.assert_frame_equal(p.drop(columns="label"), p2.drop(columns="label"), check_exact=True)
    assert d == d2 and d["trees"] == 200 and d["max_observed_depth"] <= 3
    assert d["min_leaf_unique_samples"] >= 20 and d["train_last_target"] < "1949-12"
    assert p.probability_forest.between(0, 1).all() and p.probability_naive.eq(float(train.label.mean())).all()
    assert {k: _classifier().get_params()[k] for k in FOREST_PARAMETERS} == FOREST_PARAMETERS
    single = train.copy(); single["label"] = 1
    unavailable, diagnostic = fit_forest_partition(single, test, strategy="momentum", split_id=1, year=1950, columns=SIGNAL_COLUMNS)
    assert diagnostic["status"] == "train_single_class" and unavailable.probability_forest.isna().all()
    assert unavailable.probability_naive.eq(1).all()
    empty, diagnostic = fit_forest_partition(train, test.iloc[:0], strategy="momentum", split_id=1, year=1950, columns=SIGNAL_COLUMNS)
    assert empty.empty and diagnostic["status"] == "completed"
    bad = train.copy(); bad.loc[bad.index[-1], "target_period"] = "1949-12"
    with pytest.raises(ValueError, match="purga"):
        fit_forest_partition(bad, test, strategy="momentum", split_id=1, year=1950, columns=SIGNAL_COLUMNS)
    bad = test.copy(); bad.loc[bad.index[0], SIGNAL_COLUMNS[0]] = np.nan
    with pytest.raises(ValueError, match="finitas"):
        fit_forest_partition(train, bad, strategy="momentum", split_id=1, year=1950, columns=SIGNAL_COLUMNS)


def test_forest_notebook_section_matching_history_and_invalidation(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    from sklearn.ensemble import RandomForestClassifier
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    inputs = forest_inputs()
    monkeypatch.setattr("tfm.forest.load_forest_inputs", lambda root: inputs)
    # El proveedor de prueba reduce solo el número de árboles; producción no ofrece esa opción.
    monkeypatch.setattr("tfm.forest._classifier", lambda: RandomForestClassifier(**{**FOREST_PARAMETERS, "n_estimators": 3}))
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    processed = tmp_path/"data/processed"; processed.mkdir(parents=True)
    reference = processed/"walk_forward_metrics.parquet"
    reference.write_bytes(b"existing linear result")
    namespace = {}
    notebook = json.loads((Path(__file__).parents[1]/"notebooks/14_referencia_walk_forward.ipynb").read_text())
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code" and "forest" in c.get("metadata", {}).get("tags", [])]
    assert len(cells) == 3
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:forest", "exec"), namespace)
    plt.close("all")
    assert reference.read_bytes() == b"existing linear result"
    expected_rows = (len(inputs[1]), 328, 240, 410)
    for name, count in zip(RESULT_NAMES, expected_rows):
        table, report = read_result(tmp_path, name)
        assert len(table) == count and report["experiment_status"] == "completed"
        pd.testing.assert_frame_equal(table, namespace["tablas_bosque"][name], check_exact=True)
    predictions = namespace["tablas_bosque"][RESULT_NAMES[0]]
    pd.testing.assert_frame_equal(predictions[inputs[1].columns], inputs[1], check_exact=True)
    diagnostics = namespace["tablas_bosque"][RESULT_NAMES[2]]
    assert diagnostics.trees.eq(3).all() and diagnostics.max_observed_depth.le(3).all()
    assert set(diagnostics.candidate) == set(CANDIDATE_COLUMNS)
    comparisons = namespace["tablas_bosque"][RESULT_NAMES[3]]
    np.testing.assert_allclose(comparisons.auc_improvement, comparisons.auc_candidate-comparisons.auc_reference, rtol=0, atol=0, equal_nan=True)
    np.testing.assert_allclose(comparisons.log_loss_improvement, comparisons.log_loss_reference-comparisons.log_loss_candidate, rtol=0, atol=0, equal_nan=True)
    assert all(row["expected_years"] == 40 and row["majority_required"] == 21 for row in report["stability"])
    log = tmp_path/report["trial_log"]
    events = [json.loads(l) for l in log.read_text().splitlines()]
    assert [e["status"] for e in events] == ["started", "completed"]*3
    assert all(e["candidate_configurations_per_rule"] == 1 for e in events)
    files = {processed/f"{name}.{ext}": (processed/f"{name}.{ext}").read_bytes()
             for name in RESULT_NAMES for ext in ("parquet", "json")}
    def failed(*a, **k):raise RuntimeError("Fallo de bosque simulado")
    monkeypatch.setattr("tfm.forest.fit_forest_partition", failed)
    with pytest.raises(RuntimeError, match="Fallo de bosque"):
        run_forest(tmp_path)
    assert [json.loads(l)["status"] for l in log.read_text().splitlines()][-2:] == ["started", "failed"]
    assert all(p.read_bytes() == data for p, data in files.items())
    for name in ("cpcv_regime_metrics", "logistic_metrics", "walk_forward_interaction_metrics",
                 "walk_forward_ablation_metrics", "walk_forward_economic_metrics", "validation_summary"):
        save_result(tmp_path, name, pd.DataFrame({"fixture": [1]}), {})
        assert all(p.read_bytes() == data for p, data in files.items())
    for name in ("walk_forward_predictions", "walk_forward_regime_metrics", "monthly_features", "labelled_signals"):
        for p, data in files.items():p.write_bytes(data)
        save_result(tmp_path, name, pd.DataFrame({"fixture": [1]}), {})
        assert not any(p.exists() for p in files) and log.exists()
