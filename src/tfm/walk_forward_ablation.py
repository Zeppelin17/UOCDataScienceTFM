"""Retiradas individuales de M2; diagnóstico emparejado, sin selección automática."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import pandas as pd

from tfm.logistic import MODEL_PARAMETERS
from tfm.screening import RULES
from tfm.walk_forward import (FIRST_TEST_YEAR, LAST_TEST_YEAR, M2_COLUMNS, REGIME_VARIANT,
    build_walk_forward_splits, compare_walk_forward_regime, load_walk_forward_inputs,
    load_walk_forward_regime_reference, summarize_regime_stability, summarize_walk_forward,
    summarize_walk_forward_predictions, _fit_walk_forward_partitions)


REMOVAL_MODELS = {"z_price_volatility_12m": "M2_without_volatility",
                  "z_market_return_24m": "M2_without_market_state",
                  "z_drawdown_12m": "M2_without_drawdown"}
RESULT_NAMES = ("walk_forward_ablation_predictions", "walk_forward_ablation_metrics",
                "walk_forward_ablation_coefficients", "walk_forward_ablation_comparison")


def evaluate_walk_forward_removal(samples: pd.DataFrame, reference_predictions: pd.DataFrame,
                                  removed_feature: str, *, progress=None) -> tuple[dict, dict]:
    if removed_feature not in REMOVAL_MODELS:
        raise ValueError("Solo se contemplan las tres retiradas de régimen previstas para M2.")
    model = REMOVAL_MODELS[removed_feature]
    columns = [name for name in M2_COLUMNS if name != removed_feature]
    splits = build_walk_forward_splits()
    summarize_walk_forward(samples, splits)
    reference_metrics = summarize_walk_forward_predictions(reference_predictions, models={"M2": "probability_regime"})
    fitted, coefficients, diagnostics = _fit_walk_forward_partitions(samples, splits, columns, progress=progress)
    fitted = fitted.rename(columns={"probability_logistic": "probability_without", "fit_status": "fit_status_without"})
    keys = ["split_id", "test_year", "strategy", "target_period", "label"]
    checked = [*keys, "probability_naive"]
    try:
        pd.testing.assert_frame_equal(reference_predictions[checked].sort_values(keys[:4]).reset_index(drop=True),
                                      fitted[checked].sort_values(keys[:4]).reset_index(drop=True), check_exact=True)
    except AssertionError as exc:
        raise ValueError("La retirada debe conservar las fechas, etiquetas y referencia ingenua de M2.") from exc
    predictions = reference_predictions.merge(fitted.drop(columns="probability_naive"),
                                                on=keys, how="left", validate="one_to_one")
    metrics = summarize_walk_forward_predictions(predictions, models={model: "probability_without"})
    # Positivo = mantener la variable ayuda: AUC(M2)-AUC(sin), LL(sin)-LL(M2).
    comparison = compare_walk_forward_regime(metrics, reference_metrics,
                                             reference_model=model, candidate_model="M2")
    counts = summarize_regime_stability(comparison)
    comparison = comparison.rename(columns={
        **{f"{name}_{model.lower()}": f"{name}_without" for name in ("status", "auc", "log_loss")},
        "auc_improvement": "auc_contribution", "log_loss_improvement": "log_loss_contribution",
        "auc_improved": "positive_auc_contribution"})
    for table in (predictions, metrics, coefficients, comparison):
        table.insert(0, "removed_feature", removed_feature)
        table.insert(1, "subset_model", model)
    contributions = [{"strategy": row["strategy"], "removed_feature": removed_feature,
        "expected_years": row["expected_years"], "available_years": row["auc_available_years"],
        "positive_contribution_years": row["auc_improved_years"],
        "negative_contribution_years": row["auc_worsened_years"], "tied_years": row["auc_tied_years"],
        "unavailable_years": row["auc_unavailable_years"], "majority_required": row["majority_required"],
        "positive_in_majority": row["meets_majority"]} for row in counts]
    return dict(zip(RESULT_NAMES, [predictions, metrics, coefficients, comparison])), {
        "removed_feature": removed_feature, "subset_model": model, "model_columns": columns,
        "diagnostics": diagnostics, "contributions": contributions}


def run_walk_forward_ablation(root: Path, *, progress=None) -> tuple[dict, dict]:
    """Registrar y calcular cada retirada; publicar solo si termina toda la familia."""
    samples, label_report, _ = load_walk_forward_inputs(root)
    reference, original = load_walk_forward_regime_reference(root, samples, label_report)
    batch_attempt = datetime.now(timezone.utc).isoformat()
    path = root / "outputs/experiments/walk_forward_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = {name: [] for name in RESULT_NAMES}
    variants = []
    for index, (feature, model) in enumerate(REMOVAL_MODELS.items()):
        attempt = datetime.now(timezone.utc).isoformat()
        record = {"attempt": attempt, "batch_attempt": batch_attempt,
            "variant": f"walk_forward_logistic_l2_C1_{model.lower()}_central",
            "purpose": "individual_regime_removal", "removed_feature": feature, "subset_model": model,
            "reference_variant": REGIME_VARIANT, "reference_attempt": original["attempt"],
            "baseline_attempt": original["reference_attempt"], "candidate_configurations_per_rule": 1,
            "strategies": list(RULES), "model_columns": [c for c in M2_COLUMNS if c != feature],
            "model_parameters": MODEL_PARAMETERS, "parameters": label_report["parameters"],
            "target": "label", "test_years": [FIRST_TEST_YEAR, LAST_TEST_YEAR], "guide_version": "2026-11-15"}

        def append(event):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False) + "\n")

        append({"status": "started"})
        try:
            def update(completed, total):
                if progress:
                    progress(index*total+completed, len(REMOVAL_MODELS)*total)
            tables, info = evaluate_walk_forward_removal(samples, reference["walk_forward_regime_predictions"],
                                                         feature, progress=update)
            main = tables["walk_forward_ablation_comparison"].loc[lambda t: t.aggregation.eq("pooled")]
            status = "completed" if main.comparison_status.eq("available").all() else "incomplete"
            append({"status": status, "comparison": json.loads(main.to_json(orient="records")),
                    "contributions": info["contributions"]})
        except (Exception, KeyboardInterrupt) as exc:
            append({"status": "failed", "error": str(exc)})
            raise
        for name, table in tables.items():frames[name].append(table)
        variants.append({**record, **info, "experiment_status": status})
    result = {name: pd.concat(parts, ignore_index=True) for name, parts in frames.items()}
    report = {"scope": "development_walk_forward_individual_regime_removals", "attempt": batch_attempt,
        "reference_variant": REGIME_VARIANT, "reference_attempt": original["attempt"],
        "baseline_attempt": original["reference_attempt"], "candidate_configurations_per_rule": len(REMOVAL_MODELS),
        "target": "label", "model_parameters": MODEL_PARAMETERS, "parameters": label_report["parameters"],
        "development": original["development"], "test_interval": original["test_interval"],
        "window": original["window"], "refit": "annual", "purge_months": original["purge_months"],
        "guide_version": "2026-11-15", "variants": variants,
        "experiment_status": "completed" if all(v["experiment_status"] == "completed" for v in variants) else "incomplete",
        "skill_gate_status": "diagnostic_only_no_automatic_selection_or_regime_acceptance",
        "contributions": [row for v in variants for row in v["contributions"]],
        "comparison": "positive contribution = AUC(M2)-AUC(without), log_loss(without)-log_loss(M2)",
        "versions": {name: version(name) for name in ("scikit-learn", "numpy", "pandas")},
        "trial_log": "outputs/experiments/walk_forward_trials.jsonl", "protocol": "docs/validacion_walk_forward.md",
        "warnings": ["Each subset is refitted; this is not permutation importance of a fixed model.",
                     "Conditional contribution depends on the other predictors and the chosen learning algorithm; it is not causal.",
                     "Three fixed diagnostic candidates; no post-hoc winning subset, changed sample or M3 interaction.",
                     "New selection must occur inside training before independent evaluation; no economic utility is established.",
                     "Missing annual AUC is retained; repeated examples across candidates are not independent observations."]}
    return result, report
