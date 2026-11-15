"""Selección de grupos dentro del entrenamiento exterior; protocolo del notebook 13."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.logistic import (MODEL_PARAMETERS, _sklearn, fit_logistic, fit_partition,
                         load_logistic_inputs, load_logistic_results,
                         predict_logistic, summarize_predictions)
from tfm.screening import RULES
from tfm.validation import (MODEL_COLUMNS, PURGE_MONTHS, EMBARGO_MONTHS,
                            build_temporal_splits, summarize_validation)


RESULT_NAMES = ("mda_feature_groups", "mda_logistic_predictions", "mda_logistic_monthly",
                "mda_logistic_metrics", "mda_logistic_coefficients")
VARIANT = "logistic_l2_C1_inner_clustered_mda"
CORRELATION_THRESHOLD = .70
N_REPEATS = 30
SEED = 42


def build_inner_splits(splits: pd.DataFrame) -> pd.DataFrame:
    """Conservar el calendario exterior y reservar su último bloque de entrenamiento."""
    try:
        pd.testing.assert_frame_equal(splits, build_temporal_splits()[0], check_exact=True)
    except AssertionError as exc:
        raise ValueError("Se requieren las particiones fijas del notebook 10.") from exc
    pieces = []
    for _, part in splits.groupby("split_id", sort=True):
        part = part.copy()
        outer_train = part.role.eq("train").to_numpy()
        block = int(part.loc[outer_train, "block_id"].max())
        bounds = part.loc[part.block_id.eq(block), "target_period"]
        start, end = pd.Period(bounds.iloc[0], freq="M"), pd.Period(bounds.iloc[-1], freq="M")
        months = pd.PeriodIndex(part.target_period, freq="M")
        validation = outer_train & part.block_id.eq(block).to_numpy()
        purge = ((months >= start - PURGE_MONTHS) & (months < start)
                 | (months > end) & (months <= end + PURGE_MONTHS))
        embargo = (months > end) & (months <= end + EMBARGO_MONTHS)
        roles = np.full(len(part), "outside_outer_training", dtype=object)
        roles[outer_train] = "inner_train"
        roles[outer_train & embargo] = "inner_embargo"
        roles[outer_train & purge] = "inner_purge"
        roles[validation] = "inner_validation"
        part["inner_role"] = roles
        part["inner_validation_block"] = block
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True)


def cluster_features(train: pd.DataFrame) -> tuple[list[list[str]], list[str], pd.DataFrame]:
    """Agrupar por |Spearman| >= 0,70 con enlace completo, sin etiquetas."""
    if train.empty or not np.isfinite(train[MODEL_COLUMNS].to_numpy(dtype=float)).all():
        raise ValueError("Se necesitan características internas de entrenamiento finitas.")
    constants = [name for name in MODEL_COLUMNS if train[name].nunique() <= 1]
    eligible = [name for name in MODEL_COLUMNS if name not in constants]
    if not eligible:
        return [], constants, pd.DataFrame(dtype=float)
    correlation = train[eligible].corr(method="spearman")
    if not np.isfinite(correlation.to_numpy()).all():
        raise ValueError("No se pueden estimar las correlaciones internas; no se han rellenado.")
    if len(eligible) == 1:
        return [eligible], constants, correlation
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    corr = correlation.to_numpy()
    corr = np.clip((corr + corr.T) / 2, -1, 1)
    np.fill_diagonal(corr, 1.)
    distance = np.clip(1 - np.abs(corr), 0, 1)
    tree = linkage(squareform(distance, checks=False), method="complete")
    cutoff = np.nextafter(1 - CORRELATION_THRESHOLD, np.inf)
    ids = fcluster(tree, cutoff, criterion="distance")
    groups = [[name for name, cluster in zip(eligible, ids) if cluster == group] for group in np.unique(ids)]
    groups.sort(key=lambda members: MODEL_COLUMNS.index(members[0]))
    return groups, constants, correlation


def select_groups(train: pd.DataFrame, validation: pd.DataFrame, *, strategy: str,
                   split_id: int) -> tuple[pd.DataFrame, dict]:
    """Medir la pérdida al permutar grupos en la única validación interna."""
    _, _, log_loss, roc_auc_score = _sklearn()
    for rows in (train, validation):
        if (not rows.label.isin([0, 1]).all()
                or not np.isfinite(rows[MODEL_COLUMNS].to_numpy(dtype=float)).all()):
            raise ValueError("La selección interna necesita etiquetas binarias y características finitas.")
    if set(train.target_period) & set(validation.target_period):
        raise ValueError("Entrenamiento y validación internos deben tener meses distintos.")
    records = {name: {"feature": name, "cluster_id": None, "group_members": name,
                      "mean_delta_log_loss": None, "std_delta_log_loss": None,
                      "positive_repeats": None, "permutations": 0, "selected": None,
                      "status": "selection_unavailable"} for name in MODEL_COLUMNS}
    diagnostic = {"inner_train_examples": len(train), "inner_validation_examples": len(validation),
                  "inner_train_positive": int(train.label.eq(1).sum()),
                  "inner_validation_positive": int(validation.label.eq(1).sum()),
                  "inner_model_iterations": None, "inner_log_loss": None, "inner_naive_log_loss": None,
                  "inner_auc": None, "group_count": None, "selected_columns": None,
                  "selection_status": "unavailable"}
    if train.label.nunique() == 2 and len(validation):
        groups, constants, _ = cluster_features(train)
        eligible = [name for name in MODEL_COLUMNS if name not in constants]
        model, fitted = fit_logistic(train, strategy=strategy, split_id=split_id, columns=eligible)
        prior = float(train.label.mean())
        y = validation.label.to_numpy(dtype=int)
        probabilities = predict_logistic(model, validation, columns=eligible, intercept_probability=prior)
        baseline = float(log_loss(y, probabilities, labels=[0, 1]))
        rng = np.random.default_rng(np.random.SeedSequence([SEED, split_id, RULES.index(strategy)]))
        orders = [rng.permutation(len(validation)) for _ in range(N_REPEATS)]
        for name in constants:
            records[name].update(selected=False, status="constant_in_inner_training")
        for group_id, members in enumerate(groups, 1):
            values = validation[members].to_numpy(dtype=float)
            increases = []
            for order in orders:
                changed = validation.copy()
                changed.loc[:, members] = values[order]
                p = predict_logistic(model, changed, columns=eligible, intercept_probability=prior)
                increases.append(float(log_loss(y, p, labels=[0, 1])) - baseline)
            mean = float(np.mean(increases))
            for name in members:
                records[name].update(cluster_id=group_id, group_members=", ".join(members),
                    mean_delta_log_loss=mean, std_delta_log_loss=float(np.std(increases, ddof=1)),
                    positive_repeats=int(np.sum(np.asarray(increases) > 0)), permutations=N_REPEATS,
                    selected=mean > 0, status="measured")
        diagnostic.update(inner_model_iterations=fitted["iterations"], inner_log_loss=baseline,
                          inner_naive_log_loss=float(log_loss(y, np.full(len(y), prior), labels=[0, 1])),
                          inner_auc=float(roc_auc_score(y, probabilities)) if len(np.unique(y)) == 2 else None,
                          group_count=len(groups), selected_columns=[name for name in MODEL_COLUMNS if records[name]["selected"]],
                          selection_status="completed")
    table = pd.DataFrame(list(records.values()))
    table["cluster_id"] = table.cluster_id.astype("Int64")
    table["positive_repeats"] = table.positive_repeats.astype("Int64")
    table["selected"] = table.selected.astype("boolean")
    for name in ("mean_delta_log_loss", "std_delta_log_loss"):
        table[name] = pd.to_numeric(table[name]).astype(float)
    return table, diagnostic


def evaluate_selected_partition(samples: pd.DataFrame, outer: pd.DataFrame, inner: pd.DataFrame,
                                *, strategy: str, split_id: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """El bloque exterior no entra en la agrupación ni decide las columnas."""
    rows = samples.loc[samples.strategy.eq(strategy) & samples.sample_usable]
    internal = rows.merge(inner[["target_period", "inner_role"]], on="target_period", validate="one_to_one")
    groups, selection = select_groups(internal.loc[internal.inner_role.eq("inner_train")],
                                      internal.loc[internal.inner_role.eq("inner_validation")],
                                      strategy=strategy, split_id=split_id)
    selected = selection["selected_columns"]
    external = rows.merge(outer[["target_period", "role"]], on="target_period", validate="one_to_one")
    predictions, coefficients, fitted = fit_partition(
        external.loc[external.role.eq("train")], external.loc[external.role.eq("validation")],
        strategy=strategy, split_id=split_id, columns=selected if selected is not None else [])
    if selected is None:
        predictions["probability_logistic"] = np.nan
        predictions["fit_status"] = "selection_unavailable"
        coefficients["coefficient"] = np.nan
        coefficients["fit_status"] = "selection_unavailable"
        fitted["status"] = "selection_unavailable"
    predictions["selected_feature_count"] = pd.array(
        [len(selected) if selected is not None else pd.NA] * len(predictions), dtype="Int64")
    groups.insert(0, "strategy", strategy)
    groups.insert(0, "split_id", split_id)
    diagnostic = {"split_id": split_id, "strategy": strategy,
                  "inner_validation_block": int(inner.inner_validation_block.iloc[0]), **selection,
                  "outer_train_examples": fitted["train_examples"], "outer_validation_examples": fitted["validation_examples"],
                  "outer_model_status": fitted["status"], "outer_model_iterations": fitted["iterations"]}
    return groups, predictions, coefficients, diagnostic


def evaluate_selected_logistic(samples: pd.DataFrame, splits: pd.DataFrame, *, progress=None) -> tuple[dict, dict]:
    coverage = summarize_validation(splits, samples)
    internal = build_inner_splits(splits)
    groups, predictions, coefficients, diagnostics = [], [], [], []
    for split_id, outer in splits.groupby("split_id", sort=True):
        inner = internal.loc[internal.split_id.eq(split_id)]
        for rule in RULES:
            g, p, c, d = evaluate_selected_partition(samples, outer, inner, strategy=rule, split_id=int(split_id))
            groups.append(g)
            predictions.append(p)
            coefficients.append(c)
            diagnostics.append(d)
        if progress:
            progress(int(split_id), int(splits.split_id.nunique()))
    predictions = pd.concat(predictions, ignore_index=True)
    monthly, metrics = summarize_predictions(predictions, partitions=coverage[["split_id", "strategy"]])
    if len(monthly) != int(samples.sample_usable.sum()):
        raise ValueError("La selección no conserva todos los ejemplos exteriores utilizables.")
    tables = dict(zip(RESULT_NAMES, [pd.concat(groups, ignore_index=True), predictions, monthly,
                                   metrics, pd.concat(coefficients, ignore_index=True)]))
    report = {"scope": "development_logistic_with_inner_clustered_mda", "variant": VARIANT,
              "model_parameters": MODEL_PARAMETERS, "candidate_columns": MODEL_COLUMNS, "target": "label",
              "development": ["1927-01", "1989-12"], "partitions": 15,
              "inner_policy": "last outer-training original block validates; remaining original blocks train",
              "purge_months": PURGE_MONTHS, "embargo_months": EMBARGO_MONTHS,
              "correlation": "absolute Spearman on inner training only", "linkage": "complete",
              "correlation_threshold": CORRELATION_THRESHOLD, "permutations_per_group": N_REPEATS,
              "seed": SEED, "seed_derivation": "SeedSequence([42, split_id, rule_index]); momentum=0, reversal=1",
              "selection_rule": "mean(log_loss_permuted - log_loss_original) > 0",
              "aggregation": "arithmetic mean of five outer-validation probabilities per rule and target month",
              "skill_gate_status": "pending_selected_pipeline_shadows", "diagnostics": diagnostics,
              "versions": {name: version(name) for name in ("scikit-learn", "scipy", "numpy", "pandas")},
              "warnings": ["One fixed inner holdout per outer partition; selection can depend on that period.",
                           "Group importance is specific to this fitted logistic model, not an intrinsic feature property.",
                           "Row permutations measure model reliance, not an exact time-series significance test.",
                           "The previous all-feature shadow thresholds do not validate this adaptive selection pipeline.",
                           "No final global feature list, SHAP, economic simulation or post-1989 evaluation."]}
    return tables, report


def run_clustered_mda(root: Path, *, progress=None) -> tuple[dict, dict]:
    samples, splits, label_report, preparation = load_logistic_inputs(root)
    original_metrics, original_report = load_logistic_results(root, samples, splits, label_report)
    attempt = datetime.now(timezone.utc).isoformat()
    record = {"attempt": attempt, "variant": VARIANT, "purpose": "candidate_with_inner_feature_selection",
              "candidate_configurations_per_rule": 1, "strategies": list(RULES), "target": "label",
              "original_attempt": original_report["attempt"], "model_parameters": MODEL_PARAMETERS,
              "candidate_columns": MODEL_COLUMNS, "parameters": label_report["parameters"],
              "correlation_threshold": CORRELATION_THRESHOLD, "linkage": "complete", "correlation": "absolute Spearman",
              "repeats": N_REPEATS, "seed": SEED, "inner_policy": "last available original training block validates",
              "selection_rule": "positive mean log-loss increase", "development": ["1927-01", "1989-12"]}
    path = root / "outputs/experiments/clustered_mda_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    def append(event):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False) + "\n")

    append({"status": "started"})
    try:
        tables, report = evaluate_selected_logistic(samples, splits, progress=progress)
        main = tables["mda_logistic_metrics"].loc[lambda t: t.aggregation.eq("monthly_mean")]
        status = "completed" if main.status.eq("completed").all() else "incomplete"
        append({"status": status, "metrics": json.loads(main.to_json(orient="records")),
                "selected_columns": [{"split_id": d["split_id"], "strategy": d["strategy"],
                                      "columns": d["selected_columns"]} for d in report["diagnostics"]]})
    except (Exception, KeyboardInterrupt) as exc:
        append({"status": "failed", "error": str(exc)})
        raise
    reference = original_metrics.loc[original_metrics.aggregation.eq("monthly_mean")]
    report.update(parameters=label_report["parameters"], sample_counts=preparation["sample_counts"], attempt=attempt,
                  original_attempt=original_report["attempt"], original_metrics=json.loads(reference.to_json(orient="records")),
                  experiment_status=status, trial_log="outputs/experiments/clustered_mda_trials.jsonl",
                  protocol="docs/seleccion_clustered_mda.md")
    return tables, report
