"""Separación interna, grupos correlacionados, selección vacía y flujo del notebook 13."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.clustered_mda import (RESULT_NAMES, build_inner_splits, cluster_features,
                               evaluate_selected_partition, run_clustered_mda, select_groups)
from tfm.data import read_result, save_result
from tfm.features import FEATURE_COLUMNS
from tfm.logistic import fit_partition, run_logistic_experiment
from tfm.validation import MODEL_COLUMNS, build_temporal_splits, summarize_validation
from test_logistic import PARAMETERS, fixture_samples


def test_inner_calendar_and_selection_do_not_use_outer_evaluation():
    splits, _ = build_temporal_splits()
    inner = build_inner_splits(splits)
    assert len(inner) == 11340
    for split_id, part in inner.groupby("split_id"):
        block = int(part.loc[part.role.eq("train"), "block_id"].max())
        assert part.inner_validation_block.eq(block).all()
        assert part.loc[part.inner_role.eq("inner_validation"), "block_id"].eq(block).all()
        assert part.loc[~part.role.eq("train"), "inner_role"].eq("outside_outer_training").all()
        bounds = part.loc[part.block_id.eq(block), "target_period"]
        start, end = pd.Period(bounds.iloc[0], freq="M"), pd.Period(bounds.iloc[-1], freq="M")
        training = pd.PeriodIndex(part.loc[part.inner_role.eq("inner_train"), "target_period"], freq="M")
        assert ((training < start - 1) | (training > end + 6)).all()
    _, _, samples = fixture_samples()
    rng = np.random.default_rng(123)
    x = rng.normal(size=(756, 10))
    for rule in ("momentum", "reversal"):
        mask = samples.strategy.eq(rule)
        samples.loc[mask, MODEL_COLUMNS] = x
        samples.loc[mask & samples.has_signal, "label"] = (samples.loc[mask & samples.has_signal, MODEL_COLUMNS[0]] > 0).astype(int)
    outer = splits.loc[splits.split_id.eq(1)]
    internal = inner.loc[inner.split_id.eq(1)]
    a = evaluate_selected_partition(samples, outer, internal, strategy="momentum", split_id=1)
    changed = samples.copy()
    reserved = changed.strategy.eq("momentum") & changed.sample_usable & changed.target_period.isin(
        outer.loc[outer.role.eq("validation"), "target_period"])
    changed.loc[reserved, "label"] = 1 - changed.loc[reserved, "label"]
    b = evaluate_selected_partition(changed, outer, internal, strategy="momentum", split_id=1)
    pd.testing.assert_frame_equal(a[0], b[0], check_exact=True)
    pd.testing.assert_frame_equal(a[2], b[2], check_exact=True)
    pd.testing.assert_frame_equal(a[1].drop(columns="label"), b[1].drop(columns="label"), check_exact=True)
    changed.loc[reserved, MODEL_COLUMNS] = 100.
    c = evaluate_selected_partition(changed, outer, internal, strategy="momentum", split_id=1)
    pd.testing.assert_frame_equal(a[0], c[0], check_exact=True)
    pd.testing.assert_frame_equal(a[2], c[2], check_exact=True)


def test_inverse_features_move_together_and_empty_selection_is_intercept_only(monkeypatch):
    rng = np.random.default_rng(61)
    x = rng.normal(size=(330, 10))
    x[:, 1] = -x[:, 0]
    x[:, -1] = 0.
    rows = pd.DataFrame(x, columns=MODEL_COLUMNS)
    rows["label"] = (rows[MODEL_COLUMNS[0]] > 0).astype(int)
    rows["target_period"] = pd.period_range("1927-01", periods=len(rows), freq="M").astype(str)
    train, validation = rows.iloc[:230].copy(), rows.iloc[230:].copy()
    groups, constants, _ = cluster_features(train)
    assert any(set(MODEL_COLUMNS[:2]) <= set(g) for g in groups)
    assert constants == [MODEL_COLUMNS[-1]]
    from tfm.clustered_mda import predict_logistic as real_predict
    checked = []
    def check_joint(model, data, **kwargs):
        np.testing.assert_array_equal(data[MODEL_COLUMNS[0]], -data[MODEL_COLUMNS[1]])
        checked.append(len(data))
        return real_predict(model, data, **kwargs)
    monkeypatch.setattr("tfm.clustered_mda.predict_logistic", check_joint)
    importance, diagnostic = select_groups(train, validation, strategy="momentum", split_id=1)
    signal = importance.loc[importance.feature.isin(MODEL_COLUMNS[:2])]
    assert signal.selected.all() and signal.mean_delta_log_loss.gt(0).all()
    assert signal.mean_delta_log_loss.nunique() == 1
    assert len(checked) == 1 + 30 * len(groups)
    monkeypatch.setattr("tfm.clustered_mda.predict_logistic", real_predict)
    constant = train.copy(); constant[MODEL_COLUMNS] = 1.
    empty, diagnostic = select_groups(constant, validation, strategy="momentum", split_id=1)
    assert diagnostic["selection_status"] == "completed" and diagnostic["selected_columns"] == []
    assert not empty.selected.any() and empty.mean_delta_log_loss.isna().all()
    predictions, coefficients, fitted = fit_partition(train, validation, strategy="momentum", split_id=1, columns=[])
    assert fitted["status"] == "intercept_only" and coefficients.term.tolist() == ["intercept"]
    assert predictions.probability_logistic.eq(float(train.label.mean())).all()
    assert predictions.probability_logistic.equals(predictions.probability_naive)
    single = train.copy(); single["label"] = 1
    unavailable, diagnostic = select_groups(single, validation, strategy="momentum", split_id=1)
    assert diagnostic["selection_status"] == "unavailable" and diagnostic["selected_columns"] is None
    assert unavailable.selected.isna().all()


def test_notebook_results_history_and_dependencies(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    features, labels, samples = fixture_samples()
    splits, _ = build_temporal_splits()
    summary = summarize_validation(splits, samples)
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    save_result(tmp_path, "validation_splits", splits, {})
    save_result(tmp_path, "validation_summary", summary, {})
    original_tables, original_report = run_logistic_experiment(tmp_path)
    for name, table in original_tables.items():save_result(tmp_path, name, table, original_report)
    save_result(tmp_path, "logistic_shadows", pd.DataFrame({"fixture": [1]}), {})
    save_result(tmp_path, "logistic_shadow_comparison", pd.DataFrame({"fixture": [1]}), {})
    before = {p: p.read_bytes() for p in (tmp_path / "data/processed").glob("logistic_*")}
    original_log = tmp_path / "outputs/experiments/logistic_trials.jsonl"
    original_history = original_log.read_bytes()
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/13_seleccion_clustered_mda.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "13_seleccion_clustered_mda.ipynb", "exec"), namespace)
    plt.close("all")
    report = namespace["informe"]
    assert report["experiment_status"] == "completed" and report["skill_gate_status"] == "pending_selected_pipeline_shadows"
    assert all(p.read_bytes() == content for p, content in before.items())
    assert original_log.read_bytes() == original_history
    groups, _ = read_result(tmp_path, "mda_feature_groups")
    predictions, _ = read_result(tmp_path, "mda_logistic_predictions")
    monthly, _ = read_result(tmp_path, "mda_logistic_monthly")
    metrics, _ = read_result(tmp_path, "mda_logistic_metrics")
    assert len(groups) == 300 and not groups.selected.isna().any()
    assert len(predictions) == 5 * samples.sample_usable.sum() and len(monthly) == samples.sample_usable.sum()
    assert len(metrics) == 64 and monthly.available_logistic.eq(5).all()
    assert groups.loc[groups.selected, "mean_delta_log_loss"].gt(0).all()
    assert metrics.loc[metrics.model.eq("naive"), "log_loss"].reset_index(drop=True).equals(
        original_tables["logistic_metrics"].loc[lambda t: t.model.eq("naive"), "log_loss"].reset_index(drop=True))
    log = tmp_path / report["trial_log"]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["status"] for e in events] == ["started", "completed"]
    assert events[0]["candidate_configurations_per_rule"] == 1
    def failed(*args, **kwargs):raise RuntimeError("Fallo de selección simulado")
    monkeypatch.setattr("tfm.clustered_mda.evaluate_selected_logistic", failed)
    with pytest.raises(RuntimeError, match="Fallo de selección"):
        run_clustered_mda(tmp_path)
    assert [json.loads(line)["status"] for line in log.read_text().splitlines()] == ["started", "completed", "started", "failed"]
    files = {tmp_path / "data/processed" / f"{name}.{ext}":
             (tmp_path / "data/processed" / f"{name}.{ext}").read_bytes()
             for name in RESULT_NAMES for ext in ("parquet", "json")}
    history = log.read_bytes()
    for name in ("screening_tests", "logistic_shadows", "logistic_shadow_comparison"):
        save_result(tmp_path, name, pd.DataFrame({"fixture": [2]}), {})
        assert all(p.read_bytes() == content for p, content in files.items())
    regenerations = [(name, table, original_report) for name, table in original_tables.items()]
    regenerations += [("validation_splits", splits, {}), ("labelled_signals", labels, {}), ("monthly_features", features, {})]
    for name, table, info in regenerations:
        for p, content in files.items():p.write_bytes(content)
        save_result(tmp_path, name, table, info)
        assert not any(p.exists() for p in files) and log.read_bytes() == history
