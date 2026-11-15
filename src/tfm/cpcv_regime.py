"""Robustez CPCV de los seis candidatos fijos ya estudiados con walk-forward."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.logistic import (MODEL_PARAMETERS, _sklearn, fit_partition, load_logistic_inputs,
                         summarize_predictions)
from tfm.screening import RULES
from tfm.validation import PURGE_MONTHS, EMBARGO_MONTHS, summarize_validation
from tfm.walk_forward import (SIGNAL_COLUMNS, M2_COLUMNS, M3_COLUMNS, VARIANT,
    REGIME_VARIANT, INTERACTION_VARIANT, INTERACTION_COLUMN, FIRST_TEST_YEAR,
    LAST_TEST_YEAR, build_interaction_feature)
from tfm.walk_forward_ablation import REMOVAL_MODELS


CANDIDATE_COLUMNS = {"M1": list(SIGNAL_COLUMNS), "M2": list(M2_COLUMNS), "M3": list(M3_COLUMNS),
    **{model: [c for c in M2_COLUMNS if c != feature] for feature, model in REMOVAL_MODELS.items()}}
CANDIDATE_VARIANTS = {"M1": VARIANT, "M2": REGIME_VARIANT, "M3": INTERACTION_VARIANT,
    **{model: f"walk_forward_logistic_l2_C1_{model.lower()}_central" for model in REMOVAL_MODELS.values()}}
RESULT_NAMES = ("cpcv_regime_predictions", "cpcv_regime_monthly", "cpcv_regime_metrics",
                "cpcv_regime_coefficients", "cpcv_regime_comparison")


def _common_period_metrics(monthly: pd.DataFrame) -> pd.DataFrame:
    """Mismas medias CPCV, restringidas al calendario de prueba del walk-forward."""
    _, _, log_loss, roc_auc_score = _sklearn()
    common = monthly.loc[monthly.target_period.between(f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12")]
    records = []
    for rule in RULES:
        rows = common.loc[common.strategy.eq(rule)]
        for model, column in (("logistic", "probability_logistic"), ("naive", "probability_naive")):
            y = rows.label.to_numpy(dtype=int)
            p = rows[column].to_numpy(dtype=float)
            complete = bool(len(y) and np.isfinite(p).all())
            records.append({"aggregation": "common_period", "split_id": None, "strategy": rule,
                "model": model, "examples": len(y), "positive": int(y.sum()), "negative": int(len(y)-y.sum()),
                "status": "empty_validation" if not len(y) else "completed" if complete else "unavailable_predictions",
                "log_loss": float(log_loss(y, p, labels=[0, 1])) if complete else None,
                "auc": float(roc_auc_score(y, p)) if complete and len(np.unique(y)) == 2 else None})
    result = pd.DataFrame(records)
    result["split_id"] = result.split_id.astype("Int64")
    return result


def evaluate_cpcv_candidate(samples: pd.DataFrame, splits: pd.DataFrame, model: str,
                            *, progress=None) -> tuple[dict, list[dict]]:
    if model not in CANDIDATE_COLUMNS:
        raise ValueError("Solo se evaluarán los seis candidatos CPCV previstos.")
    coverage = summarize_validation(splits, samples)
    usable = samples.loc[samples.sample_usable]
    if model == "M3" and not np.isfinite(usable[INTERACTION_COLUMN].to_numpy(dtype=float)).all():
        raise ValueError("M3 no conserva la muestra común; no se han eliminado ejemplos.")
    predictions, coefficients, diagnostics = [], [], []
    for split_id, calendar in splits.groupby("split_id", sort=True):
        for rule in RULES:
            rows = usable.loc[usable.strategy.eq(rule)].merge(calendar[["target_period", "role"]],
                on="target_period", validate="one_to_one")
            p, c, d = fit_partition(rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")],
                                    strategy=rule, split_id=int(split_id), columns=CANDIDATE_COLUMNS[model])
            predictions.append(p); coefficients.append(c); diagnostics.append(d)
        if progress:
            progress(int(split_id), int(splits.split_id.nunique()))
    predictions = pd.concat(predictions, ignore_index=True)
    keys = ["split_id", "strategy", "target_period", "label"]
    expected = splits.loc[splits.role.eq("validation"), ["split_id", "target_period"]].merge(
        usable[["strategy", "target_period", "label"]], on="target_period")
    pd.testing.assert_frame_equal(predictions[keys].sort_values(keys[:3]).reset_index(drop=True),
                                  expected[keys].sort_values(keys[:3]).reset_index(drop=True), check_exact=True)
    monthly, metrics = summarize_predictions(predictions, partitions=coverage[["split_id", "strategy"]])
    metrics = pd.concat([metrics, _common_period_metrics(monthly)], ignore_index=True)
    metrics["model"] = metrics.model.map({"logistic": model, "naive": "M0"})
    predictions = predictions.rename(columns={"probability_logistic": "probability_model"})
    monthly = monthly.rename(columns={"probability_logistic": "probability_model", "available_logistic": "available_model"})
    coefficients = pd.concat(coefficients, ignore_index=True)
    for table in (predictions, monthly, coefficients):table.insert(0, "candidate_model", model)
    return {"predictions": predictions, "monthly": monthly, "metrics": metrics, "coefficients": coefficients}, diagnostics


def compare_cpcv_models(metrics: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Seis contrastes emparejados; positivo favorece al candidato indicado."""
    pairs = [("M1", "M2", None), ("M1", "M3", None), ("M2", "M3", None),
             *[(model, "M2", feature) for feature, model in REMOVAL_MODELS.items()]]
    keys = ["aggregation", "split_id", "strategy"]
    fields = [*keys, "examples", "positive", "negative", "status", "auc", "log_loss"]
    pieces, stability = [], []
    for reference, candidate, feature in pairs:
        left = metrics.loc[metrics.model.eq(reference), fields]
        right = metrics.loc[metrics.model.eq(candidate), fields]
        rows = left.merge(right, on=keys, how="outer", validate="one_to_one",
                          suffixes=("_reference", "_candidate"), indicator=True)
        expected = {(agg, split, rule) for agg, ids in (("partition", range(1, 16)), ("monthly_mean", [0]),
                    ("common_period", [0])) for split in ids for rule in RULES}
        actual = set(zip(rows.aggregation, rows.split_id.fillna(0).astype(int), rows.strategy))
        if (actual != expected or len(rows) != len(expected) or not rows._merge.eq("both").all()
                or any(not rows[f"{name}_reference"].equals(rows[f"{name}_candidate"])
                       for name in ("examples", "positive", "negative"))):
            raise ValueError("Los candidatos CPCV deben compartir todos los periodos, ejemplos y clases.")
        complete = rows.status_reference.eq("completed") & rows.status_candidate.eq("completed")
        auc_available = complete & np.isfinite(rows[["auc_reference", "auc_candidate"]].to_numpy(dtype=float)).all(axis=1)
        loss_available = complete & np.isfinite(rows[["log_loss_reference", "log_loss_candidate"]].to_numpy(dtype=float)).all(axis=1)
        rows["auc_improvement"] = (rows.auc_candidate-rows.auc_reference).where(auc_available)
        rows["log_loss_improvement"] = (rows.log_loss_reference-rows.log_loss_candidate).where(loss_available)
        rows["auc_improved"] = rows.auc_improvement.gt(0).astype("boolean").where(auc_available)
        rows["comparison_status"] = np.select([rows.examples_reference.eq(0), ~complete, ~auc_available],
            ["empty_validation", "unavailable_predictions", "single_class"], default="available")
        rows = rows.drop(columns=["_merge", "examples_candidate", "positive_candidate", "negative_candidate"]).rename(
            columns={"examples_reference": "examples", "positive_reference": "positive", "negative_reference": "negative"})
        rows.insert(0, "reference_model", reference); rows.insert(1, "candidate_model", candidate)
        rows.insert(2, "removed_feature", feature)
        pieces.append(rows)
        for rule in RULES:
            part = rows.loc[rows.aggregation.eq("partition") & rows.strategy.eq(rule)]
            wins = int(part.auc_improved.fillna(False).sum())
            stability.append({"reference_model": reference, "candidate_model": candidate,
                "removed_feature": feature, "strategy": rule, "expected_partitions": 15,
                "available_partitions": int(part.comparison_status.eq("available").sum()),
                "improved_partitions": wins, "worsened_partitions": int(part.auc_improvement.lt(0).sum()),
                "tied_partitions": int(part.auc_improvement.eq(0).sum()),
                "unavailable_partitions": int(part.auc_improved.isna().sum()), "majority_required": 8,
                "meets_majority": wins >= 8})
    return pd.concat(pieces, ignore_index=True), stability


def run_cpcv_regime(root: Path, *, progress=None) -> tuple[dict, dict]:
    from tfm.data import read_result

    samples, splits, label_report, preparation = load_logistic_inputs(root)
    features, _ = read_result(root, "monthly_features")
    interaction = build_interaction_feature(features)
    samples = samples.merge(interaction[["target_period", INTERACTION_COLUMN]],
                            on="target_period", how="left", validate="many_to_one")
    batch = datetime.now(timezone.utc).isoformat()
    path = root / "outputs/experiments/cpcv_regime_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = {name: [] for name in ("predictions", "monthly", "metrics", "coefficients")}
    attempts, diagnostics, original_priors = {}, [], None
    for index, (model, columns) in enumerate(CANDIDATE_COLUMNS.items()):
        attempt = datetime.now(timezone.utc).isoformat(); attempts[model] = attempt
        record = {"attempt": attempt, "batch_attempt": batch, "variant": CANDIDATE_VARIANTS[model],
            "candidate_model": model, "purpose": "same_candidate_cpcv_robustness", "validation_scheme": "CPCV",
            "candidate_configurations_added_per_rule": 0, "strategies": list(RULES), "model_columns": columns,
            "model_parameters": MODEL_PARAMETERS, "parameters": label_report["parameters"], "target": "label",
            "development": ["1927-01", "1989-12"], "purge_months": PURGE_MONTHS,
            "embargo_months": EMBARGO_MONTHS, "partitions": 15, "guide_version": "2026-11-15"}
        def append(event):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False)+"\n")
        append({"status": "started"})
        try:
            def update(completed, total):
                if progress:progress(index*total+completed, len(CANDIDATE_COLUMNS)*total)
            result, fitted = evaluate_cpcv_candidate(samples, splits, model, progress=update)
            priors = result["metrics"].loc[result["metrics"].model.eq("M0")].reset_index(drop=True)
            if original_priors is None:original_priors = priors
            else:pd.testing.assert_frame_equal(priors, original_priors, check_exact=True)
            main = result["metrics"].loc[lambda t: t.aggregation.eq("monthly_mean") & t.model.eq(model)]
            status = "completed" if main.status.eq("completed").all() else "incomplete"
            append({"status": status, "metrics": json.loads(main.to_json(orient="records"))})
        except (Exception, KeyboardInterrupt) as exc:
            append({"status": "failed", "error": str(exc)}); raise
        if index:result["metrics"] = result["metrics"].loc[~result["metrics"].model.eq("M0")]
        for name, table in result.items():frames[name].append(table)
        diagnostics.extend({"candidate_model": model, **row} for row in fitted)
    tables = {name: pd.concat(parts, ignore_index=True) for name, parts in frames.items()}
    comparisons, stability = compare_cpcv_models(tables["metrics"])
    main = comparisons.loc[comparisons.aggregation.eq("monthly_mean")]
    report = {"scope": "development_matched_cpcv_regime_robustness", "attempt": batch,
        "validation_scheme": "CPCV", "model_columns": CANDIDATE_COLUMNS, "candidate_variants": CANDIDATE_VARIANTS,
        "variant_attempts": attempts, "candidate_configurations_added_per_rule": 0,
        "model_parameters": MODEL_PARAMETERS, "parameters": label_report["parameters"], "target": "label",
        "development": ["1927-01", "1989-12"], "common_period": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"],
        "partitions": 15, "purge_months": PURGE_MONTHS, "embargo_months": EMBARGO_MONTHS,
        "sample_counts": preparation["sample_counts"], "diagnostics": diagnostics, "stability": stability,
        "aggregation": "five validation probabilities per example averaged once; common period only filters these means",
        "experiment_status": "completed" if main.comparison_status.eq("available").all() else "incomplete",
        "skill_gate_status": "pending_candidate_shadows_and_economic_evaluation_no_regime_acceptance",
        "versions": {name: version(name) for name in ("scikit-learn", "numpy", "pandas")},
        "guide_version": "2026-11-15", "trial_log": "outputs/experiments/cpcv_regime_trials.jsonl",
        "protocol": "docs/cpcv_regimen.md",
        "warnings": ["Same development data and candidates already inspected; CPCV is robustness, not independent confirmation.",
                     "CPCV can train on future blocks and is not a real-time trading strategy.",
                     "Five-model means are not CPCV return paths or five independent observations.",
                     "Causal transformations, including M3, are defined by observation date before assigning blocks.",
                     "The common-period summary aligns target months, not training information or model aggregation.",
                     "No selection, shadow comparison, SHAP, economic simulation, DSR/PBO or post-1989 evaluation."]}
    return dict(zip(RESULT_NAMES, [tables["predictions"], tables["monthly"], tables["metrics"],
                                  tables["coefficients"], comparisons])), report
