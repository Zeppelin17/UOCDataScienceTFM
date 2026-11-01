"""Diez características mensuales del desarrollo; sin etiquetas ni ajuste de modelos."""

import math

import pandas as pd

from tfm.diagnostics import START, END, INDUSTRIES
from tfm.signals.shiller import price_rule_values
from tfm.sources.shiller import INSTRUMENT


FEATURE_COLUMNS = [
    "price_return_1m", "momentum_12_1", "distance_ma_3m", "distance_ma_12m",
    "price_volatility_12m", "drawdown_12m", "credit_spread_pp", "credit_spread_change_pp",
    "industry_breadth_12m", "industry_dispersion",
]

# Diccionario de salida para explicar la tabla; no configura la ejecución.
FEATURE_DESCRIPTIONS = [
    ("price_return_1m", "Retorno del último mes", "P[m] / P[m-1] - 1", "decimal", "Shiller", 0),
    ("momentum_12_1", "Momentum 12–1", "P[m-1] / P[m-12] - 1", "decimal", "Shiller", 0),
    ("distance_ma_3m", "Distancia a media de 3 meses", "P[m] / media(P[m-2:m]) - 1", "decimal", "Shiller", 0),
    ("distance_ma_12m", "Distancia a media de 12 meses", "P[m] / media(P[m-11:m]) - 1", "decimal", "Shiller", 0),
    ("price_volatility_12m", "Volatilidad anualizada", "std_muestral(r[m-11:m]) * sqrt(12)", "decimal anualizado", "Shiller", 0),
    ("drawdown_12m", "Caída desde máximo de 12 meses", "P[m] / max(P[m-11:m]) - 1", "decimal <= 0", "Shiller", 0),
    ("credit_spread_pp", "Diferencial Baa–Aaa", "BAA[k] - AAA[k]", "puntos porcentuales", "FRED / Moody's", 1),
    ("credit_spread_change_pp", "Variación mensual del diferencial", "spread[k] - spread[k-1]", "puntos porcentuales", "FRED / Moody's", 1),
    ("industry_breadth_12m", "Amplitud entre doce industrias", "media_i(W_i[k] > media(W_i[k-11:k]))", "fracción de 0 a 1", "French, ponderación por valor", 1),
    ("industry_dispersion", "Dispersión entre doce industrias", "std_muestral_i(R_i[k])", "decimal mensual", "French, ponderación por valor", 1),
]


def feature_dictionary() -> pd.DataFrame:
    return pd.DataFrame(FEATURE_DESCRIPTIONS, columns=[
        "feature", "description", "formula", "unit", "source", "extra_publication_lag_months",
    ])


def _monthly_values(table: pd.DataFrame, columns: list[str], name: str, *, positive=False) -> pd.DataFrame:
    if table.empty or not {"period", *columns} <= set(table):
        raise ValueError(f"Faltan columnas u observaciones en {name}")
    months = pd.PeriodIndex(table.period, freq="M")
    if (months.hasnans or table.period.tolist() != pd.period_range(months[0], months[-1], freq="M").astype(str).tolist()
            or months[-1] > pd.Period(END, freq="M")):
        raise ValueError(f"Meses ausentes, duplicados, desordenados o desde 1990 en {name}")
    values = table.loc[:, columns].copy()
    for column in columns:
        series = values[column]
        if (not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series)
                or series.isna().any() or not series.map(math.isfinite).all()
                or (positive and series.le(0).any())):
            raise ValueError(f"Valores inválidos o ausentes en {name}: {column}")
    values.index = months
    return values


def build_monthly_features(monthly: pd.DataFrame, industries: pd.DataFrame,
                           baa: pd.DataFrame, aaa: pd.DataFrame) -> pd.DataFrame:
    """Fila objetivo t: precios hasta t-1; crédito/industrias hasta t-2.

    El mes extra es un supuesto de publicación, no una certificación point-in-time.
    Se retienen los 756 meses; el calentamiento queda ausente y features_ready lo indica.
    No se consultan dividendos, RF, posiciones ni resultados del mes objetivo.
    """
    if "asset" not in monthly or not monthly.asset.eq(INSTRUMENT).all():
        raise ValueError("Se requieren precios de SHILLER_SP_COMPOSITE")
    prices = _monthly_values(monthly, ["price_monthly_mean"], "Shiller", positive=True).iloc[:, 0]
    sectors = _monthly_values(industries, INDUSTRIES, "industrias")
    if sectors.le(-1).any().any():
        raise ValueError("Retornos industriales <= -100 % incompatibles con índices de riqueza")
    baa_values = _monthly_values(baa, ["yield_percent"], "BAA").iloc[:, 0]
    aaa_values = _monthly_values(aaa, ["yield_percent"], "AAA").iloc[:, 0]
    if not baa_values.index.equals(aaa_values.index):
        raise ValueError("BAA y AAA no cubren los mismos meses")
    targets = pd.period_range(START, END, freq="M")
    decisions = targets - 1
    context_months = targets - 2
    # Los huecos iniciales de industrias son calentamiento; huecos interiores o finales son errores.
    if (prices.index[0] > decisions[0] - 12 or prices.index[-1] < decisions[-1]
            or sectors.index[0] > context_months[0] or sectors.index[-1] < context_months[-1]
            or baa_values.index[0] > context_months[0] - 1 or baa_values.index[-1] < context_months[-1]):
        raise ValueError("Las fuentes no cubren la historia y los meses requeridos para el desarrollo")
    rules = price_rule_values(prices)
    price_features = pd.DataFrame({
        "price_return_1m": rules.reversal_score,
        "momentum_12_1": rules.momentum_score,
        "distance_ma_3m": prices / prices.rolling(3, min_periods=3).mean() - 1,
        "distance_ma_12m": prices / prices.rolling(12, min_periods=12).mean() - 1,
        "price_volatility_12m": rules.reversal_score.rolling(12, min_periods=12).std(ddof=1) * math.sqrt(12),
        "drawdown_12m": prices / prices.rolling(12, min_periods=12).max() - 1,
    })
    spread = baa_values - aaa_values  # Los tipos entran en porcentaje; resultado en puntos porcentuales.
    wealth = (1 + sectors).cumprod()
    if not wealth.map(math.isfinite).all().all() or wealth.le(0).any().any():
        raise ValueError("Índices de riqueza industriales no positivos o no finitos")
    moving_average = wealth.rolling(12, min_periods=12).mean()
    # No convertir el calentamiento en cero: NaN > x devolvería False.
    breadth = wealth.gt(moving_average).mean(axis=1).where(moving_average.notna().all(axis=1))
    context_features = pd.DataFrame({
        "credit_spread_pp": spread, "credit_spread_change_pp": spread.diff(),
        "industry_breadth_12m": breadth, "industry_dispersion": sectors.std(axis=1, ddof=1),
    })
    table = pd.concat([
        price_features.reindex(decisions).set_axis(targets),
        context_features.reindex(context_months).set_axis(targets),
    ], axis=1).loc[:, FEATURE_COLUMNS]
    # Las únicas ausencias permitidas son los primeros meses del calentamiento de amplitud.
    for column in FEATURE_COLUMNS:
        values = table[column]
        first = values.first_valid_index()
        if (first is None or values.loc[first:].isna().any()
                or (column != "industry_breadth_12m" and values.isna().any())
                or not values.dropna().map(math.isfinite).all()):
            raise ValueError(f"Cobertura o valores calculados incompatibles en {column}")
    table.insert(0, "context_source_period", context_months.astype(str))
    table.insert(0, "price_source_period", decisions.astype(str))
    table.insert(0, "decision_period", decisions.astype(str))
    table.insert(0, "target_period", targets.astype(str))
    table.insert(0, "asset", INSTRUMENT)
    table["features_ready"] = table[FEATURE_COLUMNS].notna().all(axis=1)
    return table.reset_index(drop=True)
