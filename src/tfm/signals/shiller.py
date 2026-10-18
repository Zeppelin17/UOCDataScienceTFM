"""Señales fijas sobre promedios de Shiller, sin dividendos, ejecución o backtest."""

import math

import pandas as pd

from tfm.sources.shiller import INSTRUMENT


BASIS = "monthly_mean_price"
WARNINGS = [
    "Las señales utilizan promedios mensuales de Shiller; pueden diferir de las calculadas con cierres.",
    "Momentum positivo propone largo; momentum no positivo propone efectivo, según la configuración explícita.",
    "Las señales ausentes por falta de historia no equivalen a permanecer en efectivo.",
    "No se han calculado ejecución, dividendos, financiación, costes, rentabilidades ni etiquetas.",
]


def build_price_signals(monthly: pd.DataFrame) -> pd.DataFrame:
    """Calcular con información hasta la decisión y señalar el mes posterior.

    La entrada ya verificada puede contener historia previa; el coordinador
    limita los meses objetivo al desarrollo. No se consulta D ni un resultado
    futuro para obtener la señal.
    """
    if monthly.empty or not {"asset", "period", "price_monthly_mean"} <= set(monthly.columns):
        raise ValueError("Se requieren observaciones mensuales de Shiller con precios medios")
    table = monthly.loc[:, ["asset", "period", "price_monthly_mean"]].reset_index(drop=True)
    if not table.asset.eq(INSTRUMENT).all():
        raise ValueError("Las señales requieren SHILLER_SP_COMPOSITE")
    months = pd.PeriodIndex(table.period, freq="M")
    if table.period.tolist() != pd.period_range(months[0], months[-1], freq="M").astype(str).tolist():
        raise ValueError("Los meses deben estar ordenados, ser únicos y no tener huecos")
    prices = table.price_monthly_mean
    if (not pd.api.types.is_numeric_dtype(prices) or pd.api.types.is_bool_dtype(prices)
            or not prices.map(math.isfinite).all() or prices.le(0).any()):
        raise ValueError("Los precios medios deben ser positivos y finitos")
    momentum = prices.shift(1) / prices.shift(12) - 1
    reversal = prices / prices.shift(1) - 1
    for score in (momentum, reversal):
        if not score.dropna().map(math.isfinite).all():
            raise ValueError("La variación de precios no es finita")
    momentum_signal = pd.Series(pd.NA, index=table.index, dtype="Int8")
    reversal_signal = pd.Series(pd.NA, index=table.index, dtype="Int8")
    available = momentum.notna()
    momentum_signal.loc[available] = momentum.loc[available].gt(0).astype("int8")
    available = reversal.notna()
    reversal_signal.loc[available] = (reversal.loc[available].lt(0).astype("int8")
                                     - reversal.loc[available].gt(0).astype("int8"))
    return pd.DataFrame({
        "asset": table.asset, "decision_period": table.period,
        "target_period": (months + 1).astype(str), "basis": BASIS,
        "momentum_score": momentum, "reversal_score": reversal,
        "momentum_signal": momentum_signal, "reversal_signal": reversal_signal,
        "both_rules_available": momentum.notna() & reversal.notna(),
    })
