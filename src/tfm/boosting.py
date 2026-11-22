"""Gradient boosting con las entradas y los años de M1 y M2."""

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.forest import CANDIDATE_COLUMNS as FOREST_COLUMNS, FOREST_PARAMETERS
from tfm.logistic import model_columns
from tfm.screening import RULES
from tfm.validation import PURGE_MONTHS
from tfm.walk_forward import (FIRST_TEST_YEAR, LAST_TEST_YEAR, M2_COLUMNS, SIGNAL_COLUMNS,
    build_walk_forward_splits, compare_walk_forward_models, load_walk_forward_inputs,
    load_walk_forward_regime_reference, summarize_walk_forward_predictions)


BOOSTING_PARAMETERS = {"loss": "log_loss", "n_estimators": 100, "learning_rate": .05,
    "max_depth": 2, "min_samples_leaf": 20, "subsample": 1., "random_state": 42,
    "n_iter_no_change": None}
CANDIDATE_COLUMNS = {"GB_M1": list(SIGNAL_COLUMNS), "GB_M2": list(M2_COLUMNS)}
REFERENCE_PROBABILITIES = {"M0": "probability_naive", "L2_M1": "probability_logistic", "L2_M2": "probability_regime",
    "RF_M1": "probability_rf_m1", "RF_M2": "probability_rf_m2"}
PROBABILITIES = {**REFERENCE_PROBABILITIES, "GB_M1": "probability_gb_m1", "GB_M2": "probability_gb_m2"}
COMPARISONS = [("L2_M1", "GB_M1"), ("RF_M1", "GB_M1"), ("L2_M2", "GB_M2"),
               ("RF_M2", "GB_M2"), ("GB_M1", "GB_M2")]
RESULT_NAMES = ("boosting_walk_forward_predictions", "boosting_walk_forward_metrics",
                "boosting_walk_forward_diagnostics", "boosting_walk_forward_comparison")
KEYS = ["split_id", "test_year", "strategy", "target_period", "label"]


def _classifier():
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except ImportError as exc:
        raise ValueError('Falta scikit-learn. Instala el extra con python -m pip install -e ".[models]".') from exc
    return GradientBoostingClassifier(**BOOSTING_PARAMETERS)


def fit_boosting_partition(train: pd.DataFrame, validation: pd.DataFrame, *, strategy: str,
                             year: int, columns: list[str]) -> tuple[pd.DataFrame, dict]:
    """Ajustar la secuencia de árboles en una ventana anual de entrenamiento."""
    selected = model_columns(columns)
    if selected not in CANDIDATE_COLUMNS.values() or strategy not in RULES or not FIRST_TEST_YEAR <= year <= LAST_TEST_YEAR:
        raise ValueError("Boosting requiere las columnas de M1 o M2 y un año y regla válidos.")
    start = pd.Period(f"{year}-01", freq="M")
    if ((pd.PeriodIndex(train.target_period, freq="M") >= start - PURGE_MONTHS).any()
            or not (pd.PeriodIndex(validation.target_period, freq="M").year == year).all()):
        raise ValueError("El entrenamiento debe terminar antes del mes de purga y la prueba pertenecer al año indicado.")
    for rows in (train, validation):
        if not rows.label.isin([0, 1]).all() or not np.isfinite(rows[selected].to_numpy(dtype=float)).all():
            raise ValueError("Boosting requiere etiquetas binarias y características finitas.")

    diagnostic = {"split_id": year - FIRST_TEST_YEAR + 1, "test_year": year, "strategy": strategy,
        "train_examples": len(train), "train_positive": int(train.label.eq(1).sum()),
        "train_last_target": train.target_period.max() if len(train) else None,
        "validation_examples": len(validation), "status": "empty_training" if train.empty else "train_single_class",
        "trees": None, "max_observed_depth": None, "min_leaf_samples": None}
    probabilities = np.full(len(validation), np.nan)
    if train.label.nunique() == 2:
        model = _classifier()
        model.fit(train[selected].to_numpy(dtype=float), train.label.to_numpy(dtype=int))
        if len(validation):
            probabilities = model.predict_proba(validation[selected].to_numpy(dtype=float))[:, 1]
        trees = [estimator.tree_ for estimator in model.estimators_[:, 0]]
        diagnostic.update(status="completed", trees=len(trees), max_observed_depth=max(t.max_depth for t in trees),
            min_leaf_samples=min(int(t.n_node_samples[t.children_left == -1].min()) for t in trees))

    result = validation[["target_period", "label"]].reset_index(drop=True).assign(
        split_id=diagnostic["split_id"], test_year=year, strategy=strategy,
        probability_naive=float(train.label.mean()) if len(train) else np.nan,
        probability_boosting=probabilities, fit_status=diagnostic["status"])
    return result, diagnostic


def load_boosting_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    from tfm.data import read_result

    samples, label_report, _ = load_walk_forward_inputs(root)
    linear, report = load_walk_forward_regime_reference(root, samples, label_report)
    forest, forest_report = read_result(root, "forest_walk_forward_predictions")
    forest_metrics, forest_metrics_report = read_result(root, "forest_walk_forward_metrics")
    if (not forest_report.get("attempt") or forest_metrics_report.get("attempt") != forest_report["attempt"]
            or forest_report.get("experiment_status") != "completed"
            or forest_report.get("reference_attempt") != report["attempt"]
            or forest_report.get("baseline_attempt") != report["reference_attempt"]
            or forest_report.get("versions") != report["versions"]
            or forest_report.get("model_columns") != FOREST_COLUMNS
            or forest_report.get("model_parameters") != FOREST_PARAMETERS):
        raise ValueError("Ejecuta la sección de random forest del notebook 14 con las referencias de logística actuales.")

    shared = [*KEYS, "probability_naive", "probability_logistic", "probability_regime"]
    forest_models = {name: PROBABILITIES[name] for name in ("M0", "RF_M1", "RF_M2")}
    try:
        pd.testing.assert_frame_equal(forest[shared], linear["walk_forward_regime_predictions"][shared], check_exact=True)
        stored = forest_metrics.loc[forest_metrics.model.isin(forest_models)].reset_index(drop=True)
        computed = summarize_walk_forward_predictions(forest, models=forest_models)
        order = ["aggregation", "strategy", "test_year", "model"]
        pd.testing.assert_frame_equal(stored.sort_values(order).reset_index(drop=True),
                                      computed.sort_values(order).reset_index(drop=True), check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("Las referencias guardadas del bosque no coinciden con las señales o sus métricas.") from exc
    metadata = {"parameters": label_report["parameters"], "baseline_attempt": report["reference_attempt"],
        "reference_attempt": report["attempt"], "forest_attempt": forest_report["attempt"],
        "versions": report["versions"], "test_interval": report["test_interval"], "purge_months": report["purge_months"]}
    return samples, forest[[*KEYS, *REFERENCE_PROBABILITIES.values()]], metadata


def run_boosting(root: Path, *, progress=None) -> tuple[dict, dict]:
    samples, reference, metadata = load_boosting_inputs(root)
    splits = build_walk_forward_splits()
    batch = datetime.now(timezone.utc).isoformat()
    path = root / "outputs/experiments/boosting_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    predictions = reference.copy()
    diagnostics, attempts = [], {}
    checked = [*KEYS, "probability_naive"]
    expected = reference[checked].sort_values(KEYS).reset_index(drop=True)
    years = LAST_TEST_YEAR - FIRST_TEST_YEAR + 1

    with path.open("a", encoding="utf-8") as history:
        for index, (candidate, columns) in enumerate(CANDIDATE_COLUMNS.items()):
            attempt = datetime.now(timezone.utc).isoformat()
            attempts[candidate] = attempt
            record = {**metadata, "attempt": attempt, "batch_attempt": batch, "candidate": candidate,
                "variant": f"boosting_100_depth2_leaf20_lr005_{candidate.lower()}_central",
                "candidate_configurations_per_rule": 1, "strategies": list(RULES), "target": "label",
                "model_columns": columns, "model_parameters": BOOSTING_PARAMETERS}

            def log_event(status: str, **details) -> None:
                history.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")
                history.flush()

            log_event("started")
            try:
                parts = []
                for (split, year), calendar in splits.groupby(["split_id", "test_year"], sort=True):
                    rows = samples.loc[samples.sample_usable].merge(calendar[["target_period", "role"]],
                        on="target_period", validate="many_to_one")
                    for rule in RULES:
                        eligible = rows.loc[rows.strategy.eq(rule)]
                        fitted, diagnostic = fit_boosting_partition(eligible.loc[eligible.role.eq("train")],
                            eligible.loc[eligible.role.eq("validation")], strategy=rule, year=int(year), columns=columns)
                        parts.append(fitted)
                        diagnostics.append({"candidate": candidate, **diagnostic})
                    if progress:
                        progress(index * years + int(split), len(CANDIDATE_COLUMNS) * years)
                fitted = pd.concat(parts, ignore_index=True)
                pd.testing.assert_frame_equal(fitted[checked].sort_values(KEYS).reset_index(drop=True), expected, check_exact=True)
                probability = PROBABILITIES[candidate]
                fitted = fitted.rename(columns={"probability_boosting": probability, "fit_status": f"fit_status_{candidate.lower()}"})
                predictions = predictions.merge(fitted.drop(columns="probability_naive"), on=KEYS, validate="one_to_one")
                metrics = summarize_walk_forward_predictions(fitted, models={candidate: probability})
                pooled = metrics.loc[metrics.aggregation.eq("pooled")]
                status = "completed" if pooled.status.eq("completed").all() else "incomplete"
                log_event(status, metrics=json.loads(pooled.to_json(orient="records")))
            except (Exception, KeyboardInterrupt) as exc:
                log_event("failed", error=str(exc))
                raise

    metrics = summarize_walk_forward_predictions(predictions, models=PROBABILITIES)
    comparisons, stability = compare_walk_forward_models(metrics, COMPARISONS)
    comparison_keys = ["reference_model", "candidate_model", "strategy"]
    pooled = comparisons.loc[comparisons.aggregation.eq("pooled")].set_index(comparison_keys)
    improved = pooled.auc_improvement.gt(0) & pooled.log_loss_improvement.gt(0)
    for row in stability:
        pair = tuple(row[key] for key in comparison_keys)
        row["predictive_support"] = bool(row["meets_majority"] and improved.at[pair])
    results = dict(zip(RESULT_NAMES, [predictions, metrics, pd.DataFrame(diagnostics), comparisons]))
    return results, {**metadata, "attempt": batch, "variant_attempts": attempts,
        "scope": "development_gradient_boosting_walk_forward", "target": "label",
        "model_columns": CANDIDATE_COLUMNS, "model_parameters": BOOSTING_PARAMETERS,
        "window": "expanding", "refit": "annual", "stability": stability,
        "experiment_status": "completed" if metrics.loc[metrics.aggregation.eq("pooled"), "status"].eq("completed").all() else "incomplete",
        "trial_log": str(path.relative_to(root)), "protocol": "docs/gradient_boosting.md"}
