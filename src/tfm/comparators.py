"""Comparadores sencillos: veto bajista con información anterior al mes objetivo."""

import math

import pandas as pd

from tfm.simulation import STRATEGIES, simulate_baselines
from tfm.sources.shiller import INSTRUMENT


BEAR_LOOKBACK = 24
BEAR_STRATEGIES = {**STRATEGIES, "momentum_bear": "Momentum con filtro bajista",
                   "reversal_bear": "Reversión con filtro bajista"}
BEAR_PROTOCOL = {
    "lookback_months": BEAR_LOOKBACK, "basis": "monthly_mean_price",
    "formula": "P[m] / P[m-24] - 1 < 0; señal para m+1",
    "action": "cash_when_negative", "rules": ["momentum", "reversal"],
    "reference": "Daniel y Moskowitz (2016), DOI 10.1016/j.jfineco.2015.12.002",
}
BEAR_WARNINGS = [
    "Adaptación del indicador bajista de 24 meses a precios medios de Shiller, sin dividendos como predictor.",
    "El veto a ambas reglas es una convención del TFM, no una réplica de la estrategia dinámica del artículo.",
    "No se usa el rebote del mes objetivo ni se exige volatilidad alta; el ajuste por volatilidad sigue pendiente.",
]


def build_bear_signals(monthly: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    """Conservar la señal original y anularla si el precio cayó en 24 meses.

    Un retorno de cero permite operar. La falta de historia bloquea el cálculo,
    sin convertirse en una clasificación alcista ni reducir la muestra.
    """
    if monthly.empty or not {"asset", "period", "price_monthly_mean"} <= set(monthly):
        raise ValueError("El filtro requiere precios mensuales de Shiller")
    months = pd.PeriodIndex(monthly.period, freq="M")
    prices = monthly.price_monthly_mean
    if (monthly.period.tolist() != pd.period_range(months[0], months[-1], freq="M").astype(str).tolist()
            or not monthly.asset.eq(INSTRUMENT).all()
            or not pd.api.types.is_numeric_dtype(prices) or pd.api.types.is_bool_dtype(prices)
            or prices.isna().any() or not prices.map(math.isfinite).all() or prices.le(0).any()):
        raise ValueError("El filtro requiere precios positivos y meses consecutivos, sin duplicados")
    required = {"decision_period", "target_period", "momentum_signal", "reversal_signal"}
    if signals.empty or not required <= set(signals):
        raise ValueError("Faltan las señales originales para aplicar el filtro")
    decision = pd.PeriodIndex(signals.decision_period, freq="M")
    targets = pd.period_range(decision[0] + 1, decision[-1] + 1, freq="M").astype(str).tolist()
    if signals.target_period.tolist() != targets or signals.decision_period.tolist() != (pd.PeriodIndex(targets, freq="M") - 1).astype(str).tolist():
        raise ValueError("El filtro necesita decisiones del mes anterior, ordenadas y sin huecos")
    previous = (decision - BEAR_LOOKBACK).astype(str).tolist()
    lookup = monthly.set_index("period").price_monthly_mean
    if any(month not in lookup.index for month in [*signals.decision_period, *previous]):
        raise ValueError(f"Falta historia para el filtro de 24 meses. Prepara Shiller desde {previous[0]} o antes; no se han recortado meses.")
    result = signals.reset_index(drop=True).copy()
    result["lookback_start_period"] = previous
    result["lookback_start_price"] = lookup.loc[previous].to_numpy()
    result["decision_price"] = lookup.loc[signals.decision_period].to_numpy()
    result["market_return_24m"] = result.decision_price / result.lookback_start_price - 1
    result["bear_market"] = result.market_return_24m.lt(0)
    for rule, allowed in (("momentum", [0, 1]), ("reversal", [-1, 0, 1])):
        column = f"{rule}_signal"
        values = result[column]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or values.isna().any() or not values.isin(allowed).all()):
            raise ValueError("Faltan señales válidas; una señal ausente no equivale a efectivo")
        result[f"original_{column}"] = values.copy()
        result[column] = values.mask(result.bear_market, 0)
    return result


def simulate_bear_comparison(components: pd.DataFrame, signals: pd.DataFrame,
                             monthly: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """Las cinco cuentas comparten fechas, costes y el motor de simulación."""
    filtered = build_bear_signals(monthly, signals)
    baseline = simulate_baselines(components, signals, parameters)
    changed = simulate_baselines(components, filtered, parameters)
    changed = changed.loc[changed.strategy.ne("buy_and_hold")].copy()
    changed["strategy"] = changed.strategy.map({"momentum": "momentum_bear", "reversal": "reversal_bear"})
    result = pd.concat([baseline, changed], ignore_index=True)
    context = filtered.set_index("target_period").loc[result.period]
    for column in ("lookback_start_period", "lookback_start_price", "decision_price", "market_return_24m",
                   "bear_market", "original_momentum_signal", "original_reversal_signal"):
        result[column] = context[column].to_numpy()
    return result
