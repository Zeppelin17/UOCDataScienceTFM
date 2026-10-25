"""Escalado causal por riesgo del índice y comparación conjunta de alternativas."""

import math

import pandas as pd

from tfm.comparators import BEAR_STRATEGIES, simulate_bear_comparison, build_bear_signals
from tfm.simulation import STRATEGIES, simulate_baselines


SIMPLE_STRATEGIES = {**BEAR_STRATEGIES,
                     "buy_and_hold_volatility": "Comprar y mantener ajustado por volatilidad",
                     "momentum_volatility": "Momentum ajustado por volatilidad",
                     "reversal_volatility": "Reversión ajustada por volatilidad"}
VOLATILITY_PROTOCOL = {
    "basis": "monthly_mean_price", "estimator": "sample_std_monthly_price_returns_times_sqrt12",
    "formula": "min(max_exposure, target_annual_volatility / estimated_annual_volatility)",
    "zero_volatility": "max_exposure", "signal_lag": "decisión m; exposición en m+1",
    "reference": "Adaptación de escalado por volatilidad; Barroso y Santa-Clara (2015), DOI 10.1016/j.jfineco.2014.11.010",
}
VOLATILITY_WARNINGS = [
    "Se estima riesgo del índice con variaciones mensuales entre promedios, no riesgo diario de una cartera transversal.",
    "Se utiliza inversa de desviación típica, no la inversa de varianza de la regla principal de Moreira y Muir.",
    "El objetivo de volatilidad es una referencia de escala, no una garantía de volatilidad realizada.",
    "Las alternativas bajista y de volatilidad se comparan por separado, sin combinarlas ni optimizar sus parámetros.",
]


def validate_volatility_parameters(parameters: dict) -> None:
    required = {"lookback_months", "target_annual_volatility", "max_exposure"}
    if not isinstance(parameters, dict) or set(parameters) != required:
        raise ValueError("volatility_scaling requiere lookback_months, target_annual_volatility y max_exposure")
    window = parameters["lookback_months"]
    if type(window) is not int or window < 2:
        raise ValueError("volatility_scaling.lookback_months debe ser un entero de al menos 2")
    for key in required - {"lookback_months"}:
        value = parameters[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"volatility_scaling.{key} debe ser positivo y finito")
    if parameters["max_exposure"] > 1:
        raise ValueError("max_exposure no puede superar 1: este simulador no utiliza apalancamiento")


def build_volatility_scale(monthly: pd.DataFrame, signals: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    validate_volatility_parameters(parameters)
    # Reutiliza las comprobaciones de meses, precios y señales del comparador existente.
    # La comparación conjunta también necesita su historia de 24 meses.
    build_bear_signals(monthly, signals)
    window = parameters["lookback_months"]
    prices = monthly.set_index("period").price_monthly_mean
    returns = prices / prices.shift(1) - 1
    risk = returns.rolling(window, min_periods=window).std(ddof=1) * math.sqrt(12)
    estimates = risk.loc[signals.decision_period].reset_index(drop=True)
    if estimates.isna().any() or not estimates.map(math.isfinite).all():
        raise ValueError("Falta historia para estimar la volatilidad; amplía history_start y prepara los datos, sin recortar meses")
    scales = [min(parameters["max_exposure"], parameters["target_annual_volatility"] / value)
              if value > 0 else parameters["max_exposure"] for value in estimates]
    decisions = pd.PeriodIndex(signals.decision_period, freq="M")
    return pd.DataFrame({"decision_period": signals.decision_period.to_numpy(),
                         "target_period": signals.target_period.to_numpy(),
                         "volatility_price_start_period": (decisions - window).astype(str),
                         "estimated_annual_volatility": estimates, "volatility_scale": scales})


def simulate_simple_comparison(components: pd.DataFrame, signals: pd.DataFrame, monthly: pd.DataFrame,
                               parameters: dict, volatility_parameters: dict) -> pd.DataFrame:
    risk = build_volatility_scale(monthly, signals, volatility_parameters).set_index("target_period")
    original = simulate_bear_comparison(components, signals, monthly, parameters)
    scaled = simulate_baselines(components, signals, parameters, exposure_scale=risk.volatility_scale)
    scaled["strategy"] = scaled.strategy.map({name: f"{name}_volatility" for name in STRATEGIES})
    context_columns = [column for column in original if column not in scaled]
    context = original.loc[original.strategy.eq("buy_and_hold")].set_index("period")
    for column in context_columns:
        scaled[column] = context.loc[scaled.period, column].to_numpy()
    original["volatility_scale"] = 1.0
    scaled["volatility_scale"] = risk.loc[scaled.period, "volatility_scale"].to_numpy()
    result = pd.concat([original, scaled], ignore_index=True)
    for column in ("estimated_annual_volatility", "volatility_price_start_period"):
        result[column] = risk.loc[result.period, column].to_numpy()
    return result
