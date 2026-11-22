"""Prueba cronológica de un EBM aditivo con las entradas de M1."""

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.boosting import KEYS, PROBABILITIES, load_boosting_reference
from tfm.screening import RULES
from tfm.validation import PURGE_MONTHS
from tfm.walk_forward import (FIRST_TEST_YEAR, LAST_TEST_YEAR, SIGNAL_COLUMNS, build_walk_forward_splits,
    compare_walk_forward_models, summarize_walk_forward_predictions)


EBM_PARAMETERS = {"interactions": 0, "feature_types": ["continuous", "continuous"], "max_bins": 16,
    "max_leaves": 2, "min_samples_leaf": 20, "max_rounds": 300, "learning_rate": .03,
    "greedy_ratio": 0, "cyclic_progress": True, "smoothing_rounds": 0, "validation_size": 0,
    "early_stopping_rounds": 0, "outer_bags": 1, "inner_bags": 0, "n_jobs": 1, "random_state": 42,
    "objective": "log_loss"}
REFERENCES = {name: PROBABILITIES[name] for name in ("M0", "L2_M1", "RF_M1", "GB_M1")}
MODELS = {**REFERENCES, "EBM_M1": "probability_ebm"}
COMPARISONS = [(name, "EBM_M1") for name in REFERENCES if name != "M0"]
RESULT_NAMES = ("ebm_walk_forward_predictions", "ebm_walk_forward_metrics", "ebm_walk_forward_comparison",
                "ebm_m1_curves", "ebm_m1_local_effects")
MISSING_DEPENDENCY = 'Falta interpret-core. Instala el extra con python -m pip install -e ".[models]".'


def _classifier():
    try:
        from interpret.glassbox import ExplainableBoostingClassifier
    except ImportError as exc:
        raise ValueError(MISSING_DEPENDENCY) from exc
    return ExplainableBoostingClassifier(**EBM_PARAMETERS)


def fit_ebm_partition(train: pd.DataFrame, validation: pd.DataFrame, *, year: int):
    """Ajustar con las señales anteriores a la purga y predecir las del año objetivo."""
    if not FIRST_TEST_YEAR <= year <= LAST_TEST_YEAR:
        raise ValueError("EBM requiere un año de prueba de 1950 a 1989.")
    start = pd.Period(f"{year}-01", freq="M")
    if ((pd.PeriodIndex(train.target_period, freq="M") >= start - PURGE_MONTHS).any()
            or not (pd.PeriodIndex(validation.target_period, freq="M").year == year).all()):
        raise ValueError("El entrenamiento debe terminar antes del mes de purga y la prueba pertenecer al año indicado.")
    for rows in (train, validation):
        if not rows.label.isin([0, 1]).all() or not np.isfinite(rows[SIGNAL_COLUMNS].to_numpy(dtype=float)).all():
            raise ValueError("EBM requiere etiquetas binarias y características finitas.")
    if train.label.nunique() < 2:
        return None, np.full(len(validation), np.nan)

    model = _classifier().fit(train[SIGNAL_COLUMNS].to_numpy(dtype=float), train.label.to_numpy(dtype=int))
    if model.term_features_ != [(0,), (1,)] or model.link_ != "logit":
        raise RuntimeError("El modelo ajustado debe contener las dos aportaciones aditivas de M1 y su enlace logit.")
    probabilities = np.empty(len(validation))
    if len(validation):
        x = validation[SIGNAL_COLUMNS].to_numpy(dtype=float)
        probabilities = model.predict_proba(x)[:, 1]
    return model, probabilities


def ebm_curves(model, *, strategy: str, year: int) -> pd.DataFrame:
    """Recuperar los intervalos de entrenamiento y sus puntos en la escala de la puntuación."""
    frames = []
    for term, feature in enumerate(SIGNAL_COLUMNS):
        start, end = model.feature_bounds_[term]
        edges = np.r_[start, model.bins_[term][0], end]
        frames.append(pd.DataFrame({"strategy": strategy, "test_year": year, "feature": feature,
            "lower": edges[:-1], "upper": edges[1:], "contribution": model.term_scores_[term][1:-1],
            "examples": model.bin_weights_[term][1:-1].astype(int)}))
    return pd.concat(frames, ignore_index=True)


def run_ebm(root: Path, *, progress=None) -> tuple[dict, dict]:
    from tfm.m1_profiles import CONTEXT_MONTHS, YEARS, local_effects, m1_profile_cuts

    try:
        interpret_version = version("interpret-core")
    except PackageNotFoundError as exc:
        raise ValueError(MISSING_DEPENDENCY) from exc
    samples, references, metadata = load_boosting_reference(root)
    reference = references[[*KEYS, *REFERENCES.values()]]
    splits = build_walk_forward_splits()
    usable = samples.loc[samples.sample_usable]
    cuts = m1_profile_cuts(usable, splits)
    path = root / "outputs/experiments/ebm_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {**metadata, "attempt": datetime.now(timezone.utc).isoformat(),
        "variant": "ebm_m1_additive_bins16_leaf20_rounds300", "candidate_configurations_per_rule": 1,
        "strategies": list(RULES), "model_columns": SIGNAL_COLUMNS, "model_parameters": EBM_PARAMETERS,
        "window": "expanding", "refit": "annual", "target": "label", "interpret_core_version": interpret_version}
    forecasts, curves, effects = [], [], []
    with path.open("a", encoding="utf-8") as history:
        def log_event(status: str, **details) -> None:
            history.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")
            history.flush()

        log_event("started")
        try:
            for (split, year), calendar in splits.groupby(["split_id", "test_year"], sort=True):
                rows = usable.merge(calendar[["target_period", "role"]], on="target_period", validate="many_to_one")
                for rule in RULES:
                    eligible = rows.loc[rows.strategy.eq(rule)]
                    train = eligible.loc[eligible.role.eq("train")]
                    validation = eligible.loc[eligible.role.eq("validation")]
                    model, probabilities = fit_ebm_partition(train, validation, year=int(year))
                    forecasts.append(validation[["target_period", "label"]].assign(split_id=int(split),
                        test_year=int(year), strategy=rule, probability_ebm=probabilities))
                    if year in YEARS and model is not None:
                        curves.append(ebm_curves(model, strategy=rule, year=int(year)))
                        floor = pd.Period(f"{year}-01", freq="M") - PURGE_MONTHS - CONTEXT_MONTHS
                        context = train.loc[train.target_period.ge(str(floor))]
                        for feature in SIGNAL_COLUMNS:
                            changes, _ = local_effects(context, feature, cuts[feature].to_numpy(), model.decision_function)
                            effects.append(changes.assign(strategy=rule, test_year=int(year), feature=feature,
                                slope=changes.score_change / (changes.upper - changes.lower)))
                if progress:
                    progress(int(split), LAST_TEST_YEAR - FIRST_TEST_YEAR + 1)

            fitted = pd.concat(forecasts, ignore_index=True)
            pd.testing.assert_frame_equal(fitted[KEYS].sort_values(KEYS).reset_index(drop=True),
                reference[KEYS].sort_values(KEYS).reset_index(drop=True), check_exact=True)
            predictions = reference.merge(fitted, on=KEYS, validate="one_to_one")
            metrics = summarize_walk_forward_predictions(predictions, models=MODELS)
            comparisons, stability = compare_walk_forward_models(metrics, COMPARISONS)
            pooled = comparisons.loc[comparisons.aggregation.eq("pooled")].set_index(
                ["reference_model", "candidate_model", "strategy"])
            joint = pooled.auc_improvement.gt(0) & pooled.log_loss_improvement.gt(0)
            for row in stability:
                key = row["reference_model"], row["candidate_model"], row["strategy"]
                row["predictive_support"] = bool(row["meets_majority"] and joint.at[key])
            summary = metrics.loc[metrics.aggregation.eq("pooled") & metrics.model.eq("EBM_M1")]
            status = "completed" if summary.status.eq("completed").all() else "incomplete"
            if len(curves) != len(YEARS) * len(RULES):
                raise RuntimeError("Faltan ajustes con ambas clases para dibujar las curvas previstas.")
            tables = dict(zip(RESULT_NAMES, [predictions, metrics, comparisons, pd.concat(curves, ignore_index=True),
                                            pd.concat(effects, ignore_index=True)], strict=True))
            log_event(status, metrics=json.loads(summary.to_json(orient="records")))
        except (Exception, KeyboardInterrupt) as exc:
            log_event("failed", error=str(exc))
            raise

    return tables, {**record, "experiment_status": status, "stability": stability,
        "trial_log": str(path.relative_to(root)), "protocol": "docs/ebm_m1.md"}
