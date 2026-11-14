"""Separación de muestras, métricas manuales y recorrido del primer clasificador."""

import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.data import read_result, save_result
from tfm.features import FEATURE_COLUMNS
from tfm.logistic import RESULT_NAMES, evaluate_logistic, fit_partition, summarize_predictions
from tfm.validation import (MODEL_COLUMNS, build_temporal_splits,
                            prepare_validation_samples, summarize_validation)
from test_screening import linear_features


PARAMETERS = {"initial_capital": 100.0, "transaction_cost_rate": .001,
              "annual_borrow_rate": .01, "include_dividends": True}


def fixture_samples():
    features = linear_features()
    features.loc[:6, "industry_breadth_12m"] = np.nan
    features["features_ready"] = features[FEATURE_COLUMNS].notna().all(axis=1)
    i = np.arange(len(features))
    parts = []
    for rule, active in (("momentum", i % 3 != 0), ("reversal", i % 5 != 0)):
        part = features.copy()
        part["strategy"] = rule
        part["has_signal"] = active
        part["label_end_period"] = part.target_period
        part["label"] = pd.array(i % 2, dtype="Int8")
        part.loc[~active, "label"] = pd.NA
        part["label_no_transaction_cost"] = part.label.copy()
        part["training_ready"] = part.features_ready & active
        part["excess_return"] = np.where(active, np.where(i % 2, .01, -.01), 0.)
        parts.append(part)
    labels = pd.concat(parts, ignore_index=True)
    samples, _ = prepare_validation_samples(features, labels)
    return features, labels, samples


def test_validation_labels_do_not_affect_fit_or_predictions(monkeypatch):
    _, _, samples = fixture_samples()
    rows = samples.loc[samples.strategy.eq("momentum") & samples.sample_usable]
    train, validation = rows.iloc[:220].copy(), rows.iloc[220:].copy()
    p, c, d = fit_partition(train, validation, strategy="momentum", split_id=1)
    changed = validation.copy()
    changed["label"] = 1 - changed.label
    changed["realized_return_should_not_be_a_predictor"] = 999.
    train["realized_return_should_not_be_a_predictor"] = -999.
    p2, c2, _ = fit_partition(train, changed, strategy="momentum", split_id=1)
    pd.testing.assert_frame_equal(c, c2, check_exact=True)
    pd.testing.assert_frame_equal(p.drop(columns="label"), p2.drop(columns="label"), check_exact=True)
    assert p.probability_naive.eq(float(train.label.mean())).all()
    assert c.term.tolist() == ["intercept", *MODEL_COLUMNS] and d["status"] == "completed"
    with pytest.raises(ValueError, match="meses distintos"):
        fit_partition(train, train.iloc[:2], strategy="momentum", split_id=1)
    train["label"] = 1
    p, c, d = fit_partition(train, validation, strategy="momentum", split_id=1)
    assert d["status"] == "train_single_class" and p.probability_logistic.isna().all()
    assert c.coefficient.isna().all() and p.probability_naive.eq(1).all()
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    def nonconvergent(*args, **kwargs):
        warnings.warn("Fallo simulado", ConvergenceWarning)
    monkeypatch.setattr(LogisticRegression, "fit", nonconvergent)
    with pytest.raises(RuntimeError, match="no converge"):
        fit_partition(rows.iloc[:220], validation, strategy="momentum", split_id=1)


def test_probability_aggregation_and_metrics_against_manual_values():
    predictions = pd.DataFrame([
        {"split_id": split, "strategy": "momentum", "target_period": month, "label": label,
         "probability_logistic": probability, "probability_naive": .5}
        for split in range(1, 6)
        for month, label, probability in (("1930-08", 0, .2), ("1930-09", 1, .8))])
    monthly, metrics = summarize_predictions(predictions)
    main = metrics.loc[metrics.aggregation.eq("monthly_mean")].set_index("model")
    assert len(monthly) == 2 and monthly.validation_appearances.eq(5).all()
    assert main.loc["logistic", "log_loss"] == pytest.approx(-np.log(.8))
    assert main.loc["naive", "log_loss"] == pytest.approx(-np.log(.5))
    assert main.loc["logistic", "auc"] == 1 and main.loc["naive", "auc"] == .5
    assert main.examples.eq(2).all()
    missing = predictions.copy(); missing.loc[0, "probability_logistic"] = np.nan
    monthly, metrics = summarize_predictions(missing)
    assert pd.isna(monthly.loc[0, "probability_logistic"]) and monthly.loc[0, "available_logistic"] == 4
    assert metrics.loc[metrics.aggregation.eq("monthly_mean") & metrics.model.eq("logistic"), "log_loss"].isna().all()
    single = predictions.copy(); single["label"] = 1
    _, metrics = summarize_predictions(single)
    assert metrics.auc.isna().all() and metrics.log_loss.notna().all()
    with pytest.raises(ValueError, match="cinco predicciones"):
        summarize_predictions(predictions.iloc[1:])


def test_empty_validation_partitions_remain_in_metrics():
    features, labels, _ = fixture_samples()
    labels["has_signal"] &= labels.target_period.le("1937-06")
    labels["label"] = labels.label.where(labels.has_signal)
    labels["label_no_transaction_cost"] = labels.label_no_transaction_cost.where(labels.has_signal)
    labels["training_ready"] = labels.features_ready & labels.has_signal
    samples, _ = prepare_validation_samples(features, labels)
    splits, _ = build_temporal_splits()
    tables, report = evaluate_logistic(samples, splits)
    metrics = tables["logistic_metrics"]
    partition_metrics = metrics.loc[metrics.aggregation.eq("partition")]
    assert len(metrics) == 64 and len(partition_metrics) == 60
    assert len(partition_metrics[["split_id", "strategy"]].drop_duplicates()) == 30
    empty_pairs = {(d["split_id"], d["strategy"]) for d in report["diagnostics"]
                   if d["validation_examples"] == 0}
    empty = partition_metrics.loc[partition_metrics.status.eq("empty_validation")]
    assert len(empty_pairs) == 20 and len(empty) == 40
    assert set(zip(empty.split_id, empty.strategy)) == empty_pairs
    assert empty[["examples", "positive", "negative"]].eq(0).all().all()
    assert empty[["log_loss", "auc"]].isna().all().all()


def test_notebook_persistence_trial_history_and_invalidation(tmp_path, monkeypatch):
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
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/11_regresion_logistica.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "11_regresion_logistica.ipynb", "exec"), namespace)
    plt.close("all")
    report = namespace["informe"]
    assert report["skill_gate_status"] == "pending_model_shadows" and report["experiment_status"] == "completed"
    predictions, _ = read_result(tmp_path, "logistic_predictions")
    assert len(predictions) == 5 * samples.sample_usable.sum()
    assert predictions.probability_logistic.between(0, 1).all()
    allowed = splits.loc[splits.role.eq("validation"), ["split_id", "target_period"]]
    assert len(predictions.merge(allowed, on=["split_id", "target_period"])) == len(predictions)
    metrics, _ = read_result(tmp_path, "logistic_metrics")
    coefficients, _ = read_result(tmp_path, "logistic_coefficients")
    assert len(metrics) == 64 and len(coefficients) == 330
    log = tmp_path / report["trial_log"]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [event["status"] for event in events] == ["started", "completed"]
    assert events[0]["attempt"] == events[1]["attempt"]
    assert events[0]["candidate_configurations_per_rule"] == 1
    from tfm.logistic import run_logistic_experiment
    def failed(*args):
        raise RuntimeError("Fallo de entrenamiento simulado")
    monkeypatch.setattr("tfm.logistic.evaluate_logistic", failed)
    with pytest.raises(RuntimeError, match="Fallo de entrenamiento"):
        run_logistic_experiment(tmp_path)
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [event["status"] for event in events] == ["started", "completed", "started", "failed"]
    paths = [tmp_path / "data/processed" / f"{name}.{ext}" for name in RESULT_NAMES for ext in ("parquet", "json")]
    before = {path: path.read_bytes() for path in paths}
    save_result(tmp_path, "screening_tests", pd.DataFrame({"fixture": [1]}), {})
    assert all(path.read_bytes() == content for path, content in before.items())
    for name, table, info in (("validation_splits", splits, {}), ("validation_summary", summary, {}),
                              ("monthly_features", features, {"feature_columns": FEATURE_COLUMNS}),
                              ("labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})):
        for path, content in before.items():path.write_bytes(content)
        save_result(tmp_path, name, table, info)
        assert not any(path.exists() for path in paths)
        assert log.read_text().splitlines() == [json.dumps(event, ensure_ascii=False) for event in events]
