"""Orden cronológico, métricas con años vacíos y recorrido del notebook 14."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.data import read_result, save_result
from tfm.features import FEATURE_COLUMNS
from tfm.logistic import fit_partition
from tfm.validation import MODEL_COLUMNS
from tfm.walk_forward import (RESULT_NAMES, REGIME_RESULTS, SIGNAL_COLUMNS, M2_COLUMNS,
    build_walk_forward_splits, compare_walk_forward_regime, evaluate_walk_forward,
    evaluate_walk_forward_regime, load_walk_forward_reference, run_walk_forward,
    run_walk_forward_regime, summarize_walk_forward_predictions)
from test_logistic import PARAMETERS, fixture_samples


def test_calendar_and_predictions_do_not_learn_future_results():
    splits = build_walk_forward_splits()
    assert len(splits) == 30240 and splits.split_id.nunique() == 40
    for (_, year), part in splits.groupby(["split_id", "test_year"]):
        start = pd.Period(f"{year}-01", freq="M")
        periods = pd.PeriodIndex(part.target_period, freq="M")
        assert (periods[part.role.eq("train")] < start - 1).all()
        assert part.loc[part.role.eq("purge"), "target_period"].tolist() == [str(start - 1)]
        assert part.loc[part.role.eq("validation"), "target_period"].tolist() == pd.period_range(start, periods=12).astype(str).tolist()
        assert (periods[part.role.eq("future")] > start + 11).all()
    _, _, samples = fixture_samples()
    original, _ = evaluate_walk_forward(samples)
    changed = samples.copy()
    future = changed.target_period.ge("1955-01")
    changed.loc[future, MODEL_COLUMNS] *= 1.1
    changed.loc[future & changed.has_signal, "label"] = 1 - changed.loc[future & changed.has_signal, "label"]
    repeated, _ = evaluate_walk_forward(changed)
    for name in ("walk_forward_predictions", "walk_forward_coefficients"):
        pd.testing.assert_frame_equal(original[name].loc[lambda t: t.test_year.lt(1955)],
                                      repeated[name].loc[lambda t: t.test_year.lt(1955)], check_exact=True)
    with_regime, info = evaluate_walk_forward_regime(samples, original["walk_forward_predictions"])
    late_regime, _ = evaluate_walk_forward_regime(changed, repeated["walk_forward_predictions"])
    for name in ("walk_forward_regime_predictions", "walk_forward_regime_coefficients"):
        pd.testing.assert_frame_equal(with_regime[name].loc[lambda t: t.test_year.lt(1955)],
                                      late_regime[name].loc[lambda t: t.test_year.lt(1955)], check_exact=True)
    pd.testing.assert_frame_equal(with_regime["walk_forward_regime_predictions"][original["walk_forward_predictions"].columns],
                                  original["walk_forward_predictions"], check_exact=True)
    assert set(with_regime["walk_forward_regime_coefficients"].term) == {"intercept", *M2_COLUMNS}
    assert all(row["expected_years"] == 40 and row["majority_required"] == 21 for row in info["stability"])
    first = splits.loc[splits.test_year.eq(1950)]
    rows = samples.loc[samples.strategy.eq("momentum") & samples.sample_usable].merge(
        first[["target_period", "role"]], on="target_period", validate="one_to_one")
    train, test = rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")]
    flipped = test.copy(); flipped["label"] = 1 - flipped.label
    for columns in (SIGNAL_COLUMNS, M2_COLUMNS):
        p, c, _ = fit_partition(train, test, strategy="momentum", split_id=1, columns=columns)
        p2, c2, _ = fit_partition(train, flipped, strategy="momentum", split_id=1, columns=columns)
        pd.testing.assert_frame_equal(c, c2, check_exact=True)
        pd.testing.assert_frame_equal(p.drop(columns="label"), p2.drop(columns="label"), check_exact=True)
    assert set(original["walk_forward_coefficients"].term) == {"intercept", *SIGNAL_COLUMNS}
    predictions = original["walk_forward_predictions"]
    assert not predictions.duplicated(["strategy", "target_period"]).any()
    expected = samples.loc[samples.sample_usable & samples.target_period.ge("1950-01")]
    assert len(predictions) == len(expected)


def test_metrics_are_pooled_once_and_preserve_empty_or_single_class_years():
    predictions = pd.DataFrame([
        {"split_id": split, "test_year": year, "strategy": "momentum", "target_period": month,
         "label": y, "probability_logistic": p, "probability_naive": .5}
        for split, year, month, y, p in ((1, 1950, "1950-01", 0, .2),
                                        (1, 1950, "1950-02", 1, .8),
                                        (2, 1951, "1951-01", 1, .7))])
    metrics = summarize_walk_forward_predictions(predictions)
    assert len(metrics) == 164
    main = metrics.loc[metrics.aggregation.eq("pooled") & metrics.strategy.eq("momentum")].set_index("model")
    assert main.loc["M1", "examples"] == 3
    assert main.loc["M1", "log_loss"] == pytest.approx((-2*np.log(.8)-np.log(.7))/3)
    assert main.loc["M1", "auc"] == 1 and main.loc["M0", "auc"] == .5
    annual = metrics.loc[metrics.test_year.eq(1951) & metrics.strategy.eq("momentum")]
    assert annual.auc.isna().all() and annual.auc_status.eq("single_class").all()
    assert annual.log_loss.notna().all() and annual.status.eq("completed").all()
    empty = metrics.loc[metrics.strategy.eq("reversal")]
    assert len(empty) == 82 and empty.examples.eq(0).all()
    assert empty.status.eq("empty_validation").all() and empty.auc_status.eq("no_examples").all()
    assert empty[["log_loss", "auc"]].isna().all().all()
    missing = predictions.copy(); missing.loc[0, "probability_logistic"] = np.nan
    unavailable = summarize_walk_forward_predictions(missing)
    main = unavailable.loc[unavailable.aggregation.eq("pooled") & unavailable.strategy.eq("momentum") & unavailable.model.eq("M1")].iloc[0]
    assert main.examples == 3 and main.status == "unavailable_predictions" and pd.isna(main.log_loss)
    with pytest.raises(ValueError, match="duplicadas"):
        summarize_walk_forward_predictions(pd.concat([predictions, predictions.iloc[:1]]))
    invalid = predictions.copy(); invalid.loc[0, "test_year"] = 1952
    with pytest.raises(ValueError, match="año de prueba"):
        summarize_walk_forward_predictions(invalid)
    regime = predictions.copy()
    regime["probability_regime"] = [.8, .2, .7]
    m2_metrics = summarize_walk_forward_predictions(regime, models={"M2": "probability_regime"})
    compared = compare_walk_forward_regime(metrics, m2_metrics)
    assert len(compared) == 82
    pooled = compared.loc[compared.aggregation.eq("pooled") & compared.strategy.eq("momentum")].iloc[0]
    assert pooled.auc_improvement == -1 and pooled.log_loss_improvement < 0
    assert not pooled.auc_improved and pooled.examples == 3
    single = compared.loc[compared.test_year.eq(1951) & compared.strategy.eq("momentum")].iloc[0]
    assert single.comparison_status == "single_class" and pd.isna(single.auc_improved)
    assert single.log_loss_improvement == pytest.approx(0)
    regime.loc[0, "probability_regime"] = np.nan
    incomplete = compare_walk_forward_regime(metrics,
        summarize_walk_forward_predictions(regime, models={"M2": "probability_regime"}))
    assert incomplete.loc[incomplete.aggregation.eq("pooled") & incomplete.strategy.eq("momentum"), "comparison_status"].eq("unavailable_predictions").all()
    assert incomplete.loc[incomplete.strategy.eq("reversal"), "comparison_status"].eq("empty_validation").all()


def test_notebook_without_cpcv_inputs_and_result_dependencies(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    features, labels, samples = fixture_samples()
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    processed = tmp_path / "data/processed"
    previous = processed / "logistic_predictions.parquet"
    previous.write_bytes(b"previous experiment, must not be read or overwritten")
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    reference_before = {}
    def inspect_reference(*args, **kwargs):
        reference_before.update({p: p.read_bytes() for name in RESULT_NAMES for p in processed.glob(f"{name}.*")})
        return load_walk_forward_reference(*args, **kwargs)
    monkeypatch.setattr("tfm.walk_forward.load_walk_forward_reference", inspect_reference)
    namespace = {}
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "14_referencia_walk_forward.ipynb", "exec"), namespace)
    plt.close("all")
    assert previous.read_bytes() == b"previous experiment, must not be read or overwritten"
    assert not (processed / "validation_splits.parquet").exists()
    report = namespace["informe"]
    assert report["experiment_status"] == "completed" and report["guide_version"] == "2026-11-15"
    assert report["model_columns"] == SIGNAL_COLUMNS
    assert report["skill_gate_status"] == "pending_regime_comparisons_shadows_and_economic_evaluation"
    expected_lengths = (30240, 80, int((samples.sample_usable & samples.target_period.ge("1950-01")).sum()), 164, 240)
    for name, length in zip(RESULT_NAMES, expected_lengths):
        table, saved = read_result(tmp_path, name)
        assert len(table) == length and saved["attempt"] == report["attempt"]
    regime_report = namespace["informe_regimen"]
    assert regime_report["reference_attempt"] == report["attempt"]
    assert regime_report["model_columns"] == M2_COLUMNS and regime_report["experiment_status"] == "completed"
    assert all(p.read_bytes() == content for p, content in reference_before.items())
    for name, length in zip(REGIME_RESULTS, (expected_lengths[2], 82, 480, 82)):
        table, saved = read_result(tmp_path, name)
        assert len(table) == length and saved["reference_attempt"] == report["attempt"]
    log = tmp_path / report["trial_log"]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["status"] for e in events] == ["started", "completed", "started", "completed"]
    assert events[0]["candidate_configurations_per_rule"] == 1
    assert events[2]["candidate_configurations_per_rule"] == 1 and events[2]["variant"] != events[0]["variant"]
    report_path = processed / "walk_forward_metrics.json"
    correct = report_path.read_bytes()
    incompatible = json.loads(correct); incompatible["model_columns"] = M2_COLUMNS
    report_path.write_text(json.dumps(incompatible))
    with pytest.raises(ValueError, match="parte M0/M1"):
        run_walk_forward_regime(tmp_path)
    report_path.write_bytes(correct)
    def failed(*args, **kwargs):raise RuntimeError("Fallo cronológico simulado")
    monkeypatch.setattr("tfm.walk_forward.evaluate_walk_forward", failed)
    with pytest.raises(RuntimeError, match="Fallo cronológico"):
        run_walk_forward(tmp_path)
    assert [json.loads(line)["status"] for line in log.read_text().splitlines()] == ["started", "completed", "started", "completed", "started", "failed"]
    monkeypatch.setattr("tfm.walk_forward.evaluate_walk_forward_regime", failed)
    with pytest.raises(RuntimeError, match="Fallo cronológico"):
        run_walk_forward_regime(tmp_path)
    assert [json.loads(line)["status"] for line in log.read_text().splitlines()][-2:] == ["started", "failed"]
    history = log.read_bytes()
    files = {processed / f"{name}.{ext}": (processed / f"{name}.{ext}").read_bytes()
             for name in (*RESULT_NAMES, *REGIME_RESULTS) for ext in ("parquet", "json")}
    for name in ("screening_tests", "validation_splits", "logistic_metrics", "logistic_shadows", "mda_feature_groups"):
        save_result(tmp_path, name, pd.DataFrame({"fixture": [1]}), {})
        assert all(path.read_bytes() == content for path, content in files.items())
    for name in RESULT_NAMES:
        for path, content in files.items():path.write_bytes(content)
        save_result(tmp_path, name, namespace["tablas"][name], report)
        assert not any((processed / f"{n}.{ext}").exists() for n in REGIME_RESULTS for ext in ("parquet", "json"))
        assert all((processed / f"{n}.{ext}").exists() for n in RESULT_NAMES for ext in ("parquet", "json"))
        assert log.read_bytes() == history
    for name, table, info in (("monthly_features", features, {"feature_columns": FEATURE_COLUMNS}),
                              ("labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})):
        for path, content in files.items():path.write_bytes(content)
        save_result(tmp_path, name, table, info)
        assert not any(path.exists() for path in files) and log.read_bytes() == history
