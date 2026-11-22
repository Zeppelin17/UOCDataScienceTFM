"""Comparar listas acumuladas de variables con las pruebas cronológicas de M1."""

from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path

import pandas as pd

from tfm.clustered_mda import cluster_features
from tfm.logistic import MODEL_PARAMETERS
from tfm.screening import RULES
from tfm.validation import MODEL_COLUMNS
from tfm.walk_forward import (REGIME_COLUMNS, SIGNAL_COLUMNS, _fit_walk_forward_partitions,
    compare_walk_forward_regime, load_walk_forward_inputs, load_walk_forward_reference,
    summarize_regime_stability, summarize_walk_forward_predictions)


BLOCKS = {
    "Con_media": ["z_distance_ma_12m"],
    "Con_credito": ["z_credit_spread_pp", "z_credit_spread_change_pp"],
    "Con_industrias": ["z_industry_breadth_12m", "z_industry_dispersion"],
    "Con_regimen": REGIME_COLUMNS,
}
VARIANTS = {candidate: f"walk_forward_logistic_l2_{candidate.lower()}_central" for candidate in BLOCKS}
PREDICTION_KEYS = ["split_id", "test_year", "strategy", "target_period", "label", "probability_naive"]
CLUSTER_THRESHOLD = .80
NEAR_THRESHOLD = .70


def training_correlations(samples: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """Describir la estabilidad de las parejas calculadas en cada entrenamiento."""
    usable = samples.loc[samples.sample_usable, ["target_period", "strategy", *MODEL_COLUMNS]]
    records = []
    for year, calendar in splits.loc[splits.role.eq("train")].groupby("test_year", sort=True):
        past = usable.loc[usable.target_period.isin(calendar.target_period)]
        for rule in RULES:
            train = past.loc[past.strategy.eq(rule)]
            groups, _, correlation = (cluster_features(train, threshold=CLUSTER_THRESHOLD)
                                      if len(train) else ([], [], pd.DataFrame()))
            membership = {feature: index for index, group in enumerate(groups) for feature in group}
            for left, right in combinations(MODEL_COLUMNS, 2):
                available = left in membership and right in membership
                rho = correlation.at[left, right] if available else float("nan")
                records.append({"test_year": int(year), "strategy": rule, "feature_a": left,
                    "feature_b": right, "spearman": rho,
                    "same_cluster": available and membership[left] == membership[right]})
    return pd.DataFrame(records)


def summarize_training_correlations(correlations: pd.DataFrame) -> pd.DataFrame:
    rho = correlations.spearman
    return correlations.assign(near=rho.abs().between(NEAR_THRESHOLD, CLUSTER_THRESHOLD, inclusive="left"),
        strong=rho.abs().ge(CLUSTER_THRESHOLD)).groupby(["strategy", "feature_a", "feature_b"], as_index=False).agg(
            median_spearman=("spearman", "median"), years_available=("spearman", "count"),
            years_near=("near", "sum"), years_strong=("strong", "sum"), years_grouped=("same_cluster", "sum")
        ).sort_values(["strategy", "years_grouped", "years_strong", "years_near"], ascending=[True, False, False, False])


def fit_feature_block(samples: pd.DataFrame, splits: pd.DataFrame, reference: pd.DataFrame,
                      columns: list[str]) -> pd.DataFrame:
    """Reproducir las probabilidades de un bloque en la muestra común de M1."""
    fitted, _, _ = _fit_walk_forward_partitions(samples, splits, columns)
    order = PREDICTION_KEYS[:4]
    pd.testing.assert_frame_equal(fitted[PREDICTION_KEYS].sort_values(order).reset_index(drop=True),
                                  reference[PREDICTION_KEYS].sort_values(order).reset_index(drop=True),
                                  check_exact=True)
    return fitted


def run_feature_blocks(root: Path) -> dict:
    samples, label_report, _ = load_walk_forward_inputs(root)
    baseline, report = load_walk_forward_reference(root, samples, label_report)
    splits = baseline["walk_forward_splits"]
    correlations = training_correlations(samples, splits)
    reference = "M1"
    reference_metrics = baseline["walk_forward_metrics"]
    columns = list(SIGNAL_COLUMNS)
    keys = PREDICTION_KEYS
    predictions = baseline["walk_forward_predictions"].copy()
    comparisons, stability = [], []
    path = root / "outputs/experiments/walk_forward_block_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as history:
        for candidate, added in BLOCKS.items():
            columns.extend(added)
            record = {"attempt": datetime.now(timezone.utc).isoformat(),
                "variant": VARIANTS[candidate], "candidate": candidate,
                "reference_model": reference, "reference_attempt": report["attempt"],
                "candidate_configurations_per_rule": 1, "strategies": list(RULES), "target": "label",
                "model_columns": columns, "model_parameters": MODEL_PARAMETERS,
                "parameters": label_report["parameters"], "test_interval": report["test_interval"],
                "purge_months": report["purge_months"], "window": "expanding", "refit": "annual"}

            def log_event(status: str, **details) -> None:
                history.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")
                history.flush()

            log_event("started")
            try:
                fitted = fit_feature_block(samples, splits, predictions, columns)
                probability = f"probability_{candidate.lower()}"
                fitted = fitted.rename(columns={"probability_logistic": probability})
                metrics = summarize_walk_forward_predictions(fitted, models={candidate: probability})
                difference = compare_walk_forward_regime(reference_metrics, metrics,
                    reference_model=reference, candidate_model=candidate)
                difference = difference.rename(columns={f"{field}_{model.lower()}": f"{field}_{suffix}"
                    for model, suffix in ((reference, "reference"), (candidate, "candidate"))
                    for field in ("status", "auc", "log_loss")})
                difference.insert(0, "reference_model", reference)
                difference.insert(1, "candidate_model", candidate)
                comparisons.append(difference)
                stability.extend({"candidate_model": candidate, **row} for row in summarize_regime_stability(difference))
                predictions = predictions.merge(fitted[[*keys, probability]], on=keys, validate="one_to_one")
                pooled = metrics.loc[metrics.aggregation.eq("pooled")]
                status = "completed" if pooled.status.eq("completed").all() else "incomplete"
                log_event(status, metrics=json.loads(pooled.to_json(orient="records")))
            except (Exception, KeyboardInterrupt) as exc:
                log_event("failed", error=str(exc))
                raise
            reference, reference_metrics = candidate, metrics

    comparison = pd.concat(comparisons, ignore_index=True)
    summary = comparison.loc[comparison.aggregation.eq("pooled")].merge(pd.DataFrame(stability),
        on=["candidate_model", "strategy"], validate="one_to_one")
    summary["predictive_support"] = (summary.auc_improvement.gt(0) & summary.log_loss_improvement.gt(0)
                                    & summary.meets_majority)
    return {"predictions": predictions, "summary": summary, "comparisons": comparison,
            "correlations": correlations, "correlation_summary": summarize_training_correlations(correlations)}
