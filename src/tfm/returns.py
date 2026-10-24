"""Componentes mensuales sobre Shiller y RF; todavía sin posiciones ni costes."""

import math

import pandas as pd

from tfm.preparation.french import validate_rf
from tfm.sources.shiller import INSTRUMENT


COLUMNS = ["asset", "period", "previous_period", "price_previous_month", "price_monthly_mean",
           "dividend_annualized", "dividend_monthly_approx", "price_return",
           "dividend_return_approx", "total_return_approx", "rf_return"]
FORMULAS = {"price_return": "P[t] / P[t-1] - 1",
            "dividend_monthly_approx": "D[t] / 12",
            "dividend_return_approx": "(D[t] / 12) / P[t-1]",
            "total_return_approx": "price_return + dividend_return_approx",
            "rf_return": "RF[t] / 100 (porcentaje mensual en el CSV original)"}
WARNINGS = ["Variaciones entre promedios de Shiller; no son retornos de operaciones ejecutables.",
            "D/12 es una aproximación contable, no un pago mensual observado ni información necesariamente conocida entonces.",
            "RF es un resultado del mes; no se utiliza como predictor del mismo mes.",
            "No se han aplicado señales, negociación, préstamo, financiación ni costes; no hay resultados de estrategias."]


def build_return_components(monthly: pd.DataFrame, rf: pd.DataFrame, *, start: str, end: str) -> pd.DataFrame:
    first = pd.Period(start, freq="M") - 1
    expected = pd.period_range(first, end, freq="M").astype(str).tolist()
    required = {"asset", "period", "price_monthly_mean", "dividend_annualized"}
    if not required <= set(monthly.columns):
        raise ValueError("Faltan columnas de Shiller para preparar las rentabilidades")
    window = monthly.loc[monthly.period.between(str(first), end), sorted(required)].reset_index(drop=True)
    if window.period.tolist() != expected or not window.asset.eq(INSTRUMENT).all():
        raise ValueError("Se necesita un precio por mes del desarrollo y el mes anterior, sin huecos ni duplicados")
    for name in ("price_monthly_mean", "dividend_annualized"):
        values = window[name]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or not values.map(math.isfinite).all()
                or (values.le(0).any() if name == "price_monthly_mean" else values.lt(0).any())):
            raise ValueError("Los precios y dividendos de Shiller deben ser finitos y válidos")
    validate_rf(rf, start=start, end=end)
    result = window.iloc[1:].reset_index(drop=True).copy()
    result["previous_period"] = window.period.iloc[:-1].to_numpy()
    result["price_previous_month"] = window.price_monthly_mean.iloc[:-1].to_numpy()
    result["dividend_monthly_approx"] = result.dividend_annualized / 12
    result["price_return"] = result.price_monthly_mean / result.price_previous_month - 1
    result["dividend_return_approx"] = result.dividend_monthly_approx / result.price_previous_month
    result["total_return_approx"] = result.price_return + result.dividend_return_approx
    # Las fechas se exigen idénticas antes de alinear; no hacer un inner join que pierda meses.
    if result.period.tolist() != rf.period.tolist():
        raise ValueError("Shiller y RF deben tener exactamente los mismos meses")
    result["rf_return"] = rf.rf_return.to_numpy()
    for name in ("dividend_monthly_approx", "price_return", "dividend_return_approx", "total_return_approx"):
        if not result[name].map(math.isfinite).all():
            raise ValueError("El cálculo de rentabilidades produjo un valor no finito")
    return result[COLUMNS]
