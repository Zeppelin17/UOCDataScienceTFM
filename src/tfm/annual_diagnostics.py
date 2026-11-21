"""Diagnóstico anual descriptivo de predicciones guardadas; sin nuevos ajustes."""

from pathlib import Path

import numpy as np
import pandas as pd

from tfm.walk_forward import FIRST_TEST_YEAR, LAST_TEST_YEAR, summarize_walk_forward_predictions


MODELS = {
    "M0": "probability_naive",
    "L2_M1": "probability_logistic",
    "L2_M2": "probability_regime",
    "L2_M3": "probability_interaction",
    "RF_M1": "probability_rf_m1",
    "RF_M2": "probability_rf_m2",
    "RF_M3": "probability_rf_m3",
}
CONTEXT_COLUMNS = ["market_return_24m", "price_volatility_12m", "drawdown_12m"]
KEYS = ["split_id", "test_year", "strategy", "target_period", "label"]


def build_annual_diagnostics(predictions: pd.DataFrame, features: pd.DataFrame) -> dict:
    """Conservar cuarenta años, incluso vacíos, y separar calendario y señales."""
    months = pd.period_range(f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12", freq="M")
    required = ["target_period", "decision_period", *CONTEXT_COLUMNS]
    if (not set(required) <= set(features) or features.target_period.duplicated().any()
            or features.target_period.gt(f"{LAST_TEST_YEAR}-12").any()):
        raise ValueError("Se necesitan características únicas del desarrollo anterior a 1990.")
    context = features.loc[features.target_period.isin(months.astype(str)), required].copy()
    context = context.sort_values("target_period").reset_index(drop=True)
    if (context.target_period.tolist() != months.astype(str).tolist()
            or context.decision_period.tolist() != (months-1).astype(str).tolist()
            or not np.isfinite(context[CONTEXT_COLUMNS].to_numpy(dtype=float)).all()
            or context.price_volatility_12m.lt(0).any() or context.drawdown_12m.gt(0).any()):
        raise ValueError("El contexto requiere doce meses por año y precios anteriores al objetivo.")
    metrics = summarize_walk_forward_predictions(predictions, models=MODELS)
    context["test_year"] = months.year
    context["bear_month"] = context.market_return_24m.lt(0)
    market = context.groupby("test_year", as_index=False).agg(
        calendar_months=("target_period", "size"), bear_months=("bear_month", "sum"),
        mean_volatility_12m=("price_volatility_12m", "mean"),
        mean_drawdown_12m=("drawdown_12m", "mean"))
    active = predictions[KEYS].merge(
        context.drop(columns="test_year"), on="target_period", how="left", validate="many_to_one")
    active_context = active.groupby(["strategy", "test_year"], as_index=False).agg(
        active_bear_months=("bear_month", "sum"),
        active_mean_volatility_12m=("price_volatility_12m", "mean"),
        active_mean_drawdown_12m=("drawdown_12m", "mean"))
    annual = metrics.loc[metrics.aggregation.eq("year")].reset_index(drop=True)
    operations = annual.loc[annual.model.eq("M0"),
        ["test_year", "strategy", "examples", "positive", "negative", "auc_status"]].merge(
            active_context, on=["strategy", "test_year"], how="left", validate="one_to_one")
    operations["active_bear_months"] = operations.active_bear_months.fillna(0).astype(int)
    return {"annual": annual, "pooled": metrics.loc[metrics.aggregation.eq("pooled")].reset_index(drop=True),
            "operations": operations, "market": market}


def load_annual_diagnostics(root: Path) -> dict:
    """Leer salidas del 14 y contrastarlas sin entrenar, publicar o descargar."""
    from tfm.data import read_result

    forest, forest_report = read_result(root, "forest_walk_forward_predictions")
    logistic, logistic_report = read_result(root, "walk_forward_interaction_predictions")
    features, _ = read_result(root, "monthly_features")
    coverage, baseline_report = read_result(root, "walk_forward_summary")
    if (not forest_report.get("reference_attempt")
            or forest_report.get("reference_attempt") != logistic_report.get("reference_attempt")
            or forest_report.get("baseline_attempt") != logistic_report.get("baseline_attempt")
            or forest_report.get("baseline_attempt") != baseline_report.get("attempt")):
        raise ValueError("El diagnóstico requiere logística y bosque con las mismas referencias del 14.")
    shared = [*KEYS, "probability_naive", "probability_logistic", "probability_regime"]
    try:
        pd.testing.assert_frame_equal(forest[shared].sort_values(KEYS).reset_index(drop=True),
            logistic[shared].sort_values(KEYS).reset_index(drop=True), check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("Las predicciones de logística y bosque deben compartir señales y referencias.") from exc
    predictions = forest.merge(logistic[[*KEYS, "probability_interaction"]], on=KEYS,
                               how="left", validate="one_to_one")
    result = build_annual_diagnostics(predictions, features)
    try:
        observed = result["operations"].sort_values(["strategy", "test_year"])
        expected = coverage.sort_values(["strategy", "test_year"])
        pd.testing.assert_frame_equal(observed[["strategy", "test_year", "examples", "positive"]].reset_index(drop=True),
            expected[["strategy", "test_year", "validation_examples", "validation_positive"]].rename(
                columns={"validation_examples": "examples", "validation_positive": "positive"}).reset_index(drop=True),
            check_exact=True, check_dtype=False)
        computed = pd.concat([result["annual"], result["pooled"]], ignore_index=True)
        families = {
            "walk_forward_metrics": {"M0": "M0", "M1": "L2_M1"},
            "walk_forward_regime_metrics": {"M2": "L2_M2"},
            "walk_forward_interaction_metrics": {"M3": "L2_M3"},
            "forest_walk_forward_metrics": {m: m for m in ("M0", "RF_M1", "RF_M2", "RF_M3")},
        }
        for name, names in families.items():
            stored, _ = read_result(root, name)
            stored = stored.assign(model=stored.model.map(names))
            keys = ["aggregation", "strategy", "test_year", "model"]
            current = computed.loc[computed.model.isin(names.values())]
            pd.testing.assert_frame_equal(current.sort_values(keys).reset_index(drop=True),
                stored.sort_values(keys).reset_index(drop=True), check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("Las métricas o recuentos guardados no coinciden con las predicciones actuales del 14.") from exc
    return result
