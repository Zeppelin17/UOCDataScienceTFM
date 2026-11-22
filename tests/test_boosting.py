"""Aislamiento temporal y comparación emparejada de las variantes de boosting."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.boosting import (BOOSTING_PARAMETERS, PROBABILITIES, RESULT_NAMES, fit_boosting_partition,
                          run_boosting)
from tfm.data import read_result, save_result
from tfm.forest import CANDIDATE_COLUMNS as FOREST_COLUMNS, FOREST_PARAMETERS
from tfm.walk_forward import SIGNAL_COLUMNS, summarize_walk_forward_predictions
from test_forest import forest_inputs


def test_boosting_uses_only_training_labels_and_respects_purge():
    samples, _, _, _ = forest_inputs()
    rows = samples.loc[samples.sample_usable & samples.strategy.eq("momentum")]
    train = rows.loc[rows.target_period.lt("1949-12")]
    validation = rows.loc[rows.target_period.between("1950-01", "1950-12")]
    settings = {"strategy": "momentum", "year": 1950, "columns": SIGNAL_COLUMNS}
    prediction, diagnostic = fit_boosting_partition(train, validation, **settings)
    flipped, _ = fit_boosting_partition(train, validation.assign(label=1-validation.label), **settings)
    np.testing.assert_array_equal(prediction.probability_boosting, flipped.probability_boosting)
    assert diagnostic["trees"] == BOOSTING_PARAMETERS["n_estimators"]
    assert diagnostic["max_observed_depth"] <= BOOSTING_PARAMETERS["max_depth"]
    assert diagnostic["min_leaf_samples"] >= BOOSTING_PARAMETERS["min_samples_leaf"]
    with pytest.raises(ValueError, match="purga"):
        fit_boosting_partition(train.assign(target_period="1949-12"), validation, **settings)


def test_boosting_notebook_validates_and_preserves_reference_predictions(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    from sklearn.ensemble import GradientBoostingClassifier

    samples, linear, parameters, _ = forest_inputs()
    reference = {"attempt": "linear", "reference_attempt": "baseline", "versions": {},
                 "test_interval": ["1950-01", "1989-12"], "purge_months": 1}
    forest = linear.assign(probability_rf_m1=.49, probability_rf_m2=.48)
    forest_models = {model: PROBABILITIES[model] for model in ("M0", "RF_M1", "RF_M2")}
    forest_metrics = summarize_walk_forward_predictions(forest, models=forest_models)
    forest_report = {"attempt": "forest", "reference_attempt": "linear", "baseline_attempt": "baseline",
        "versions": {}, "model_columns": FOREST_COLUMNS, "model_parameters": FOREST_PARAMETERS,
        "experiment_status": "completed"}
    save_result(tmp_path, "forest_walk_forward_predictions", forest, forest_report)
    save_result(tmp_path, "forest_walk_forward_metrics", forest_metrics, forest_report)
    monkeypatch.setattr("tfm.boosting.load_walk_forward_inputs", lambda root: (samples, {"parameters": parameters}, {}))
    monkeypatch.setattr("tfm.boosting.load_walk_forward_regime_reference",
        lambda root, samples, report: ({"walk_forward_regime_predictions": linear}, reference))
    monkeypatch.setattr("tfm.boosting._classifier",
        lambda: GradientBoostingClassifier(**{**BOOSTING_PARAMETERS, "n_estimators": 3}))
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    notebook = json.loads((Path(__file__).parents[1]/"notebooks/14_referencia_walk_forward.ipynb").read_text())
    cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"
             and "boosting" in cell.get("metadata", {}).get("tags", [])]
    assert len(cells) == 3
    namespace = {}
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:boosting", "exec"), namespace)
    for name, count in zip(RESULT_NAMES, (len(linear), 574, 160, 410), strict=True):
        saved, report = read_result(tmp_path, name)
        assert len(saved) == count and report["forest_attempt"] == "forest"
        pd.testing.assert_frame_equal(saved, namespace["tablas_boosting"][name], check_exact=True)
    forecasts = namespace["tablas_boosting"][RESULT_NAMES[0]]
    pd.testing.assert_frame_equal(forecasts[forest.columns], forest, check_exact=True)
    summary = namespace["resumen_boosting"]
    np.testing.assert_array_equal(summary.predictive_support,
        summary.meets_majority & summary.auc_improvement.gt(0) & summary.log_loss_improvement.gt(0))
    history = tmp_path / report["trial_log"]
    events = [json.loads(line) for line in history.read_text().splitlines()]
    assert [event["status"] for event in events] == ["started", "completed"] * 2
    save_result(tmp_path, "forest_walk_forward_metrics", forest_metrics, {**forest_report, "attempt": "other"})
    assert not any((tmp_path / f"data/processed/{name}.parquet").exists() for name in RESULT_NAMES)
    with pytest.raises(ValueError, match="sección de random forest"):
        run_boosting(tmp_path)
    assert len(history.read_text().splitlines()) == 4
