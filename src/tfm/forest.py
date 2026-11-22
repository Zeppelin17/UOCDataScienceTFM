"""Random forest pequeño, con listas fijas y el calendario walk-forward existente."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.logistic import model_columns
from tfm.screening import RULES
from tfm.validation import PURGE_MONTHS
from tfm.walk_forward import (FIRST_TEST_YEAR, LAST_TEST_YEAR, SIGNAL_COLUMNS, M2_COLUMNS,
    M3_COLUMNS, INTERACTION_COLUMN, build_interaction_feature, build_walk_forward_splits,
    load_walk_forward_inputs, load_walk_forward_regime_reference, summarize_walk_forward,
    summarize_walk_forward_predictions, compare_walk_forward_models)


FOREST_PARAMETERS = {"n_estimators": 200, "criterion": "gini", "max_depth": 3,
    "min_samples_split": 2, "min_samples_leaf": 20, "max_features": 1.0,
    "bootstrap": True, "max_samples": None, "class_weight": None, "random_state": 42,
    "n_jobs": 1, "max_leaf_nodes": None, "min_impurity_decrease": 0.0, "ccp_alpha": 0.0}
CANDIDATE_COLUMNS = {"RF_M1": list(SIGNAL_COLUMNS), "RF_M2": list(M2_COLUMNS), "RF_M3": list(M3_COLUMNS)}
VARIANTS = {model: f"forest_depth3_leaf20_trees200_{model.lower()}_central" for model in CANDIDATE_COLUMNS}
PROBABILITIES = {model: f"probability_{model.lower()}" for model in CANDIDATE_COLUMNS}
RESULT_NAMES = ("forest_walk_forward_predictions", "forest_walk_forward_metrics",
                "forest_walk_forward_diagnostics", "forest_walk_forward_comparison")


def _classifier():
    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError as exc:
        raise ValueError('Falta scikit-learn. Instala el extra con python -m pip install -e ".[models]".') from exc
    return RandomForestClassifier(**FOREST_PARAMETERS)


def fit_forest_partition(train: pd.DataFrame, validation: pd.DataFrame, *, strategy: str,
                          split_id: int, year: int, columns: list[str]) -> tuple[pd.DataFrame, dict]:
    """Divisiones del árbol aprendidas solo antes de diciembre previo a la prueba."""
    selected = model_columns(columns)
    if (not selected or strategy not in RULES or not FIRST_TEST_YEAR <= year <= LAST_TEST_YEAR
            or split_id != year-FIRST_TEST_YEAR+1):
        raise ValueError("Se necesitan columnas y un año walk-forward válidos.")
    cutoff = pd.Period(f"{year}-01", freq="M")-PURGE_MONTHS
    if ((pd.PeriodIndex(train.target_period, freq="M") >= cutoff).any()
            or not (pd.PeriodIndex(validation.target_period, freq="M").year == year).all()):
        raise ValueError("El entrenamiento debe terminar antes del mes de purga y la prueba pertenecer al año indicado.")
    for rows in (train, validation):
        if (not rows.label.isin([0, 1]).all()
                or not np.isfinite(rows[selected].to_numpy(dtype=float)).all()):
            raise ValueError("El bosque requiere etiquetas binarias y características finitas.")
    diagnostic = {"split_id": split_id, "test_year": year, "strategy": strategy,
        "train_examples": len(train), "train_positive": int(train.label.eq(1).sum()),
        "train_first_target": str(train.target_period.min()) if len(train) else None,
        "train_last_target": str(train.target_period.max()) if len(train) else None,
        "validation_examples": len(validation), "status": "empty_training" if train.empty else "train_single_class",
        "trees": None, "max_observed_depth": None, "mean_leaves": None, "min_leaf_unique_samples": None}
    probabilities = np.full(len(validation), np.nan)
    if train.label.nunique() == 2:
        model = _classifier()
        model.fit(train[selected].to_numpy(dtype=float), train.label.to_numpy(dtype=int))
        if len(validation):
            positive = int(np.flatnonzero(model.classes_ == 1)[0])
            probabilities = model.predict_proba(validation[selected].to_numpy(dtype=float))[:, positive]
        diagnostic.update(status="completed", trees=len(model.estimators_),
            max_observed_depth=max(t.tree_.max_depth for t in model.estimators_),
            mean_leaves=float(np.mean([t.tree_.n_leaves for t in model.estimators_])),
            min_leaf_unique_samples=min(int(t.tree_.n_node_samples[t.tree_.children_left == -1].min())
                                        for t in model.estimators_))
    result = validation[["target_period", "label"]].reset_index(drop=True).copy()
    result.insert(0, "strategy", strategy); result.insert(0, "test_year", year)
    result.insert(0, "split_id", split_id)
    result["probability_naive"] = float(train.label.mean()) if len(train) else np.nan
    result["probability_forest"] = probabilities
    result["fit_status_forest"] = diagnostic["status"]
    return result, diagnostic


def load_forest_inputs(root: Path) -> tuple:
    from tfm.data import read_result

    samples, label_report, _ = load_walk_forward_inputs(root)
    reference, report = load_walk_forward_regime_reference(root, samples, label_report)
    features, _ = read_result(root, "monthly_features")
    interaction = build_interaction_feature(features)
    samples = samples.merge(interaction[["target_period", INTERACTION_COLUMN]],
                            on="target_period", how="left", validate="many_to_one")
    if not np.isfinite(samples.loc[samples.sample_usable, INTERACTION_COLUMN].to_numpy(dtype=float)).all():
        raise ValueError("RF_M3 debe conservar toda la muestra común, sin eliminar ejemplos.")
    return samples, reference["walk_forward_regime_predictions"], label_report["parameters"], report


def _compare_forest(metrics: pd.DataFrame, reference_predictions: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    linear = summarize_walk_forward_predictions(reference_predictions,
        models={"L2_M1": "probability_logistic", "L2_M2": "probability_regime"})
    combined = pd.concat([metrics, linear], ignore_index=True)
    pairs = [("RF_M1", "RF_M2"), ("RF_M1", "RF_M3"), ("RF_M2", "RF_M3"),
             ("L2_M1", "RF_M1"), ("L2_M2", "RF_M2")]
    return compare_walk_forward_models(combined, pairs)


def run_forest(root: Path, *, progress=None) -> tuple[dict, dict]:
    samples, reference, parameters, original = load_forest_inputs(root)
    splits = build_walk_forward_splits()
    summarize_walk_forward(samples, splits)
    batch = datetime.now(timezone.utc).isoformat()
    path = root/"outputs/experiments/forest_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    predictions = reference.copy()
    scores = [summarize_walk_forward_predictions(reference, models={"M0": "probability_naive"})]
    diagnostics, attempts = [], {}
    keys = ["split_id", "test_year", "strategy", "target_period", "label"]
    for index, (candidate, columns) in enumerate(CANDIDATE_COLUMNS.items()):
        attempt = datetime.now(timezone.utc).isoformat(); attempts[candidate] = attempt
        record = {"attempt": attempt, "batch_attempt": batch, "variant": VARIANTS[candidate],
            "candidate": candidate, "purpose": "fixed_small_random_forest_walk_forward",
            "candidate_configurations_per_rule": 1, "strategies": list(RULES), "target": "label",
            "model_parameters": FOREST_PARAMETERS, "model_columns": columns, "parameters": parameters,
            "reference_attempt": original["attempt"], "baseline_attempt": original["reference_attempt"],
            "test_interval": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"],
            "purge_months": PURGE_MONTHS, "window": "expanding", "refit": "annual", "guide_version": "2026-11-15"}
        def append(event):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False)+"\n")
        append({"status": "started"})
        try:
            pieces = []
            for (split, year), calendar in splits.groupby(["split_id", "test_year"], sort=True):
                for rule in RULES:
                    rows = samples.loc[samples.sample_usable & samples.strategy.eq(rule)].merge(
                        calendar[["target_period", "role"]], on="target_period", validate="one_to_one")
                    p, d = fit_forest_partition(rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")],
                        strategy=rule, split_id=int(split), year=int(year), columns=columns)
                    pieces.append(p); diagnostics.append({"candidate": candidate, **d})
                if progress:
                    years = LAST_TEST_YEAR-FIRST_TEST_YEAR+1
                    progress(index*years+int(split), len(CANDIDATE_COLUMNS)*years)
            fitted = pd.concat(pieces, ignore_index=True)
            checked = [*keys, "probability_naive"]
            pd.testing.assert_frame_equal(fitted[checked].sort_values(keys[:4]).reset_index(drop=True),
                                          reference[checked].sort_values(keys[:4]).reset_index(drop=True), check_exact=True)
            fitted = fitted.rename(columns={"probability_forest": PROBABILITIES[candidate],
                                             "fit_status_forest": f"fit_status_{candidate.lower()}"})
            metrics = summarize_walk_forward_predictions(fitted, models={candidate: PROBABILITIES[candidate]})
            main = metrics.loc[metrics.aggregation.eq("pooled")]
            status = "completed" if main.status.eq("completed").all() else "incomplete"
            append({"status": status, "metrics": json.loads(main.to_json(orient="records"))})
        except (Exception, KeyboardInterrupt) as exc:
            append({"status": "failed", "error": str(exc)}); raise
        predictions = predictions.merge(fitted.drop(columns="probability_naive"), on=keys, how="left", validate="one_to_one")
        scores.append(metrics)
    metrics = pd.concat(scores, ignore_index=True)
    comparisons, stability = _compare_forest(metrics, reference)
    status = "completed" if metrics.loc[metrics.aggregation.eq("pooled"), "status"].eq("completed").all() else "incomplete"
    report = {"scope": "development_small_random_forest_walk_forward", "attempt": batch,
        "variant_attempts": attempts, "variants": VARIANTS, "model_columns": CANDIDATE_COLUMNS,
        "model_parameters": FOREST_PARAMETERS, "parameters": parameters, "target": "label",
        "reference_attempt": original["attempt"], "baseline_attempt": original["reference_attempt"],
        "development": ["1927-01", "1989-12"], "test_interval": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"],
        "window": "expanding", "refit": "annual", "purge_months": PURGE_MONTHS,
        "stability": stability, "experiment_status": status,
        "skill_gate_status": "pending_forest_cpcv_shadows_and_economic_evaluation_no_regime_acceptance",
        "versions": {name: version(name) for name in ("scikit-learn", "numpy", "pandas")},
        "guide_version": "2026-11-15", "trial_log": str(path.relative_to(root)), "protocol": "docs/random_forest.md",
        "warnings": ["Parameters fixed after inspecting logistic results, before first forest fit; no hyperparameter search.",
            "Same sample, causal preparation and calendar as the linear reference; no post-1989 data.",
            "RF_M2 can already represent interactions; RF_M3 adds an explicit feature representation.",
            "Three new candidates per rule; trees and years are not independent configurations.",
            "No calibration, automatic selection, coefficients, Gini importance, MDA, SHAP or economic evaluation.",
            "Logistic shadow results do not validate random forest; predictive differences do not accept regimes."]}
    return dict(zip(RESULT_NAMES, [predictions, metrics, pd.DataFrame(diagnostics), comparisons])), report
