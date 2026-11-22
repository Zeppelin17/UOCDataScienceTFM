"""Sombras circulares del M1 de momentum sobre las particiones CPCV guardadas."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.cpcv_regime import RESULT_NAMES as CPCV_RESULTS
from tfm.diagnostics import START, END
from tfm.logistic import MODEL_PARAMETERS, fit_partition, load_logistic_inputs, summarize_predictions
from tfm.model_shadows import (AUC_REFERENCE, QUANTILE_METHOD, SHADOW_QUANTILE,
                               circular_shifts, compare_shadows, model_calendar)
from tfm.screening import MIN_SHIFT
from tfm.validation import EMBARGO_MONTHS, PURGE_MONTHS
from tfm.walk_forward import SIGNAL_COLUMNS, VARIANT


RULE = "momentum"
RESULT_NAMES = ("momentum_m1_shadows", "momentum_m1_shadow_comparison")


def load_momentum_shadow_inputs(root: Path) -> tuple:
    from tfm.data import read_result

    samples, splits, label_report, _ = load_logistic_inputs(root)
    predictions, pred_report = read_result(root, CPCV_RESULTS[0])
    metrics, report = read_result(root, CPCV_RESULTS[2])
    versions = {name: version(name) for name in ("scikit-learn", "numpy", "pandas")}
    if (not report.get("attempt") or pred_report.get("attempt") != report["attempt"]
            or not report.get("variant_attempts", {}).get("M1") or report.get("experiment_status") != "completed"
            or report.get("candidate_variants", {}).get("M1") != VARIANT
            or report.get("model_columns", {}).get("M1") != SIGNAL_COLUMNS
            or report.get("model_parameters") != MODEL_PARAMETERS
            or report.get("parameters") != label_report["parameters"] or report.get("versions") != versions
            or report.get("development") != [START, END] or report.get("purge_months") != PURGE_MONTHS
            or report.get("embargo_months") != EMBARGO_MONTHS or report.get("partitions") != splits.split_id.nunique()):
        raise ValueError("Ejecuta las secciones 16–18 del notebook 14 con las entradas actuales antes del contraste.")
    original = predictions.loc[predictions.candidate_model.eq("M1") & predictions.strategy.eq(RULE)]
    original = original.drop(columns="candidate_model").rename(columns={"probability_model": "probability_logistic"})
    baseline = metrics.loc[metrics.strategy.eq(RULE) & metrics.model.isin(["M0", "M1"])
                           & metrics.aggregation.ne("common_period")].copy()
    baseline["model"] = baseline.model.map({"M0": "naive", "M1": "logistic"})
    return samples, splits, original, baseline, report


def momentum_folds(samples: pd.DataFrame, splits: pd.DataFrame, calendar: pd.DataFrame) -> list:
    """Emparejar fechas una vez y fijar la posición de cada señal en el calendario común."""
    index = pd.Series(np.arange(len(calendar)), index=calendar.target_period)
    usable = samples.loc[samples.strategy.eq(RULE) & samples.sample_usable, ["target_period", "label"]].copy()
    usable["feature_index"] = usable.target_period.map(index)
    if usable.feature_index.isna().any():
        raise ValueError("Faltan señales activas en el calendario de las sombras de M1.")
    folds = []
    for split, dates in splits.groupby("split_id", sort=True):
        rows = usable.merge(dates[["target_period", "role"]], on="target_period", validate="one_to_one")
        folds.append((int(split), rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")]))
    return folds


def evaluate_momentum_shadow(folds: list, values: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Repetir los mismos ajustes y el resumen CPCV para las columnas indicadas."""
    pieces, completed = [], 0
    for split, train, validation in folds:
        prepared_train = train[["target_period", "label"]].copy()
        prepared_validation = validation[["target_period", "label"]].copy()
        prepared_train[SIGNAL_COLUMNS] = values[train.feature_index.to_numpy(dtype=int)]
        prepared_validation[SIGNAL_COLUMNS] = values[validation.feature_index.to_numpy(dtype=int)]
        prediction, _, diagnostic = fit_partition(prepared_train, prepared_validation, strategy=RULE,
                                                  split_id=split, columns=SIGNAL_COLUMNS)
        pieces.append(prediction)
        completed += diagnostic["status"] == "completed"
    predictions = pd.concat(pieces, ignore_index=True)
    partitions = pd.DataFrame({"split_id": [fold[0] for fold in folds], "strategy": RULE})
    _, metrics = summarize_predictions(predictions, partitions=partitions)
    return predictions, metrics, completed


def run_momentum_shadows(root: Path, *, progress=None) -> tuple[dict, dict]:
    samples, splits, original, baseline, previous = load_momentum_shadow_inputs(root)
    calendar = model_calendar(samples)
    shifts = circular_shifts(len(calendar))
    values = calendar[SIGNAL_COLUMNS].to_numpy(dtype=float)
    folds = momentum_folds(samples, splits, calendar)
    recreated, metrics, reference_fits = evaluate_momentum_shadow(folds, values)
    try:
        pd.testing.assert_frame_equal(recreated, original.reset_index(drop=True), check_exact=True)
        pd.testing.assert_frame_equal(metrics, baseline.reset_index(drop=True), check_exact=True)
    except AssertionError as exc:
        raise ValueError("M1 no reproduce las predicciones CPCV guardadas para las mismas señales.") from exc
    naive = baseline.loc[baseline.model.eq("naive")].reset_index(drop=True)
    naive_loss = float(naive.loc[naive.aggregation.eq("monthly_mean"), "log_loss"].iloc[0])

    path = root / "outputs/experiments/momentum_m1_shadow_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"attempt": datetime.now(timezone.utc).isoformat(), "purpose": "circular_shadow_reference",
        "reference_variant": VARIANT, "reference_attempt": previous["variant_attempts"]["M1"],
        "cpcv_attempt": previous["attempt"], "strategy": RULE, "model_columns": SIGNAL_COLUMNS,
        "model_parameters": MODEL_PARAMETERS, "parameters": previous["parameters"], "versions": previous["versions"],
        "development": [START, END], "common_months": len(calendar), "common_start": calendar.target_period.iloc[0],
        "common_end": calendar.target_period.iloc[-1], "shift_months": shifts, "minimum_circular_distance": MIN_SHIFT,
        "partitions": len(folds), "purge_months": PURGE_MONTHS, "embargo_months": EMBARGO_MONTHS,
        "expected_fits": len(shifts) * len(folds), "reference_fits": reference_fits, "candidate_configurations_added": 0,
        "auc_reference": AUC_REFERENCE, "shadow_quantile": SHADOW_QUANTILE, "quantile_method": QUANTILE_METHOD}
    records, shift = [], None
    with path.open("a", encoding="utf-8") as history:
        def log_event(status: str, **details) -> None:
            history.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")
            history.flush()

        log_event("started")
        try:
            for index, shift in enumerate(shifts, 1):
                _, scores, completed = evaluate_momentum_shadow(folds, np.roll(values, shift, axis=0))
                pd.testing.assert_frame_equal(scores.loc[scores.model.eq("naive")].reset_index(drop=True), naive, check_exact=True)
                score = scores.loc[scores.aggregation.eq("monthly_mean") & scores.model.eq("logistic")].iloc[0]
                available = (score.status == "completed" and completed == len(folds)
                             and np.isfinite([score.log_loss, score.auc]).all())
                records.append({"shift_months": shift, "circular_distance_months": min(shift, len(calendar)-shift),
                    "strategy": RULE, "examples": int(score.examples), "log_loss": score.log_loss, "auc": score.auc,
                    "naive_log_loss": naive_loss, "log_loss_improvement": naive_loss-score.log_loss,
                    "completed_fits": completed, "status": "completed" if available else "unavailable"})
                if progress and (index % 25 == 0 or index == len(shifts)):
                    progress(index, len(shifts))
            shadows = pd.DataFrame(records)
            comparison, summary = compare_shadows(shadows, baseline, shifts, rules=(RULE,))
            status = "completed" if summary["shadow_comparison_available"] else "incomplete"
            log_event(status, comparison=json.loads(comparison.to_json(orient="records")))
        except (Exception, KeyboardInterrupt) as exc:
            log_event("failed", shift_months_at_failure=shift, error=str(exc))
            raise
    return dict(zip(RESULT_NAMES, [shadows, comparison], strict=True)), {
        **record, **summary, "experiment_status": status, "trial_log": str(path.relative_to(root)),
        "protocol": "docs/sombras_momentum_m1.md"}
