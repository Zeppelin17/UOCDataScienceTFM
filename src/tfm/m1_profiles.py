"""Diagnóstico de las formas aprendidas por M1 en el desarrollo cronológico."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit

from tfm.boosting import (BOOSTING_PARAMETERS, CANDIDATE_COLUMNS, KEYS, PROBABILITIES,
                          _classifier as make_boosting, load_boosting_inputs)
from tfm.forest import _classifier as make_forest
from tfm.logistic import fit_logistic
from tfm.screening import RULES
from tfm.walk_forward import SIGNAL_COLUMNS, build_walk_forward_splits


YEARS = (1959, 1969, 1979, 1989)
MODELS = ("L2_M1", "RF_M1", "GB_M1")
QUANTILES = (.10, .30, .50, .70, .90)
MIN_EXAMPLES = 8
CONTEXT_MONTHS = 120
PROBABILITY_FLOOR = 1e-6


def local_effects(rows: pd.DataFrame, feature: str, edges: np.ndarray, score) -> tuple[pd.DataFrame, np.ndarray]:
    """Calcular diferencias emparejadas y acumularlas desde el corte central."""
    if len(edges) != len(QUANTILES) or not np.isfinite(edges).all() or np.any(np.diff(edges) <= 0):
        raise ValueError("El diagnóstico requiere cinco cortes finitos y distintos.")
    intervals = pd.cut(rows[feature], edges, labels=False, include_lowest=True)
    records = []
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:], strict=True)):
        local = rows.loc[intervals.eq(index), SIGNAL_COLUMNS]
        change = np.nan
        if len(local) >= MIN_EXAMPLES:
            low = local.assign(**{feature: lower}).to_numpy(dtype=float)
            high = local.assign(**{feature: upper}).to_numpy(dtype=float)
            change = float(np.mean(score(high) - score(low)))
        records.append({"lower": lower, "upper": upper, "examples": len(local), "score_change": change})
    effects = pd.DataFrame(records)
    changes = effects.score_change.to_numpy()
    center = len(edges) // 2
    anchor = 0. if np.isfinite(changes[center-1:center+1]).any() else np.nan
    cumulative = np.r_[-np.cumsum(changes[:center][::-1])[::-1], anchor, np.cumsum(changes[center:])]
    return effects, cumulative


def _score(model, rows: np.ndarray) -> np.ndarray:
    if hasattr(model, "decision_function"):
        return model.decision_function(rows)
    return logit(np.clip(model.predict_proba(rows)[:, 1], PROBABILITY_FLOOR, 1 - PROBABILITY_FLOOR))


def run_m1_profiles(root: Path) -> dict[str, pd.DataFrame]:
    from tfm.data import read_result

    samples, reference, linked = load_boosting_inputs(root)
    predictions, report = read_result(root, "boosting_walk_forward_predictions")
    attempts = ("baseline_attempt", "reference_attempt", "forest_attempt", "versions")
    if (any(report.get(key) != linked[key] for key in attempts) or report.get("experiment_status") != "completed"
            or report.get("model_parameters") != BOOSTING_PARAMETERS or report.get("model_columns") != CANDIDATE_COLUMNS):
        raise ValueError("Ejecuta las secciones 32–34 del notebook 14 con las referencias actuales.")
    pd.testing.assert_frame_equal(predictions[reference.columns], reference, check_exact=True)

    splits = build_walk_forward_splits()
    first_train = splits.loc[splits.test_year.eq(YEARS[0]) & splits.role.eq("train"), "target_period"]
    usable = samples.loc[samples.sample_usable]
    first_months = usable.loc[usable.target_period.isin(first_train)].drop_duplicates("target_period")
    cuts = first_months[SIGNAL_COLUMNS].quantile(QUANTILES)
    intervals, curves, fits = [], [], []
    for (split, year), calendar in splits.loc[splits.test_year.isin(YEARS)].groupby(["split_id", "test_year"], sort=True):
        rows = usable.merge(calendar[["target_period", "role"]], on="target_period", validate="many_to_one")
        last = pd.Period(calendar.loc[calendar.role.eq("train"), "target_period"].iloc[-1], freq="M")
        first = last - CONTEXT_MONTHS + 1
        for rule in RULES:
            eligible = rows.loc[rows.strategy.eq(rule)]
            train = eligible.loc[eligible.role.eq("train")]
            context = train.loc[train.target_period.ge(str(first))]
            validation = eligible.loc[eligible.role.eq("validation"), ["target_period", "label", *SIGNAL_COLUMNS]]
            check = predictions.loc[predictions.test_year.eq(year) & predictions.strategy.eq(rule)]
            pd.testing.assert_frame_equal(check[["target_period", "label"]].reset_index(drop=True),
                validation[["target_period", "label"]].reset_index(drop=True), check_exact=True)
            linear, _ = fit_logistic(train, strategy=rule, split_id=int(split), columns=SIGNAL_COLUMNS)
            if linear is None:
                raise ValueError(f"El ajuste de {rule} para {year} requiere ambas clases de entrenamiento.")
            x = train[SIGNAL_COLUMNS].to_numpy(dtype=float)
            y = train.label.to_numpy(dtype=int)
            fitted = (linear, make_forest().fit(x, y), make_boosting().fit(x, y))
            fits.append({"strategy": rule, "test_year": int(year), "context_start": str(first), "context_end": str(last),
                         "training_examples": len(train), "context_examples": len(context), "checked_predictions": len(check)})
            for name, model in zip(MODELS, fitted, strict=True):
                if len(validation):
                    forecast = model.predict_proba(validation[SIGNAL_COLUMNS].to_numpy(dtype=float))[:, 1]
                    np.testing.assert_allclose(forecast, check[PROBABILITIES[name]], rtol=0, atol=1e-12,
                                               err_msg=f"La reproducción difiere en {rule}, {year}, {name}.")
                for feature in SIGNAL_COLUMNS:
                    edges = cuts[feature].to_numpy()
                    changes, profile = local_effects(context, feature, edges, lambda values: _score(model, values))
                    keys = {"strategy": rule, "test_year": int(year), "model": name, "feature": feature}
                    intervals.append(changes.assign(**keys))
                    curves.append(pd.DataFrame({**keys, "value": edges, "effect": profile}))
    return {"intervals": pd.concat(intervals, ignore_index=True), "curves": pd.concat(curves, ignore_index=True),
            "fits": pd.DataFrame(fits)}
