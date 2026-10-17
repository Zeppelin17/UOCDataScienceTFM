"""Motor diario largo/efectivo; las exposiciones recibidas son efectivas al cierre."""

import math

import pandas as pd


def validate_prices(prices: pd.DataFrame) -> None:
    """Rechazar datos incompatibles sin ordenarlos, rellenarlos o corregirlos."""
    if not prices.columns.is_unique or not {"asset", "observed_at", "adjusted_close"}.issubset(prices.columns):
        raise ValueError("Faltan columnas únicas de activo, fecha o cierre ajustado")
    if prices.empty or not prices["asset"].eq("SPY").all():
        raise ValueError("Se esperaban precios de un único activo: SPY")
    dates = prices["observed_at"]
    if not pd.api.types.is_datetime64_any_dtype(dates) or dates.dt.tz is not None:
        raise ValueError("Se esperaban fechas de sesión sin zona horaria")
    if (dates.isna().any() or not dates.is_unique or not dates.is_monotonic_increasing
            or not dates.eq(dates.dt.normalize()).all()):
        raise ValueError("Fechas de sesión ausentes, duplicadas, desordenadas o con horas")
    values = prices["adjusted_close"]
    if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
            or values.isna().any() or not values.map(math.isfinite).all() or values.le(0).any()):
        raise ValueError("Los cierres ajustados deben ser positivos y finitos")


def simulate_long_cash(prices: pd.DataFrame, target_exposure: pd.Series, *, cost_bps: float) -> pd.DataFrame:
    """Simular exposiciones binarias, sin préstamo, con efectivo no remunerado.

    Primero se aplica el retorno con la exposición anterior; después se negocia
    al cierre y se deduce su coste. El generador de posiciones debe resolver el
    retraso entre decisión y ejecución. La primera fila parte de efectivo y no
    permite una entrada. No se liquida automáticamente en la última fila.
    """
    validate_prices(prices)
    if len(prices) < 2:
        raise ValueError("La simulación requiere al menos dos sesiones")
    if (not isinstance(target_exposure, pd.Series) or not target_exposure.index.equals(prices.index)
            or target_exposure.isna().any() or not target_exposure.isin([0, 1]).all()
            or target_exposure.iloc[0] != 0):
        raise ValueError("Exposición 0/1 alineada con precios y primera sesión en efectivo requerida")
    if (isinstance(cost_bps, bool) or not isinstance(cost_bps, (int, float))
            or not math.isfinite(cost_bps) or not 0 <= cost_bps < 10000):
        raise ValueError("El coste debe ser finito, no negativo y menor que 10.000 puntos básicos")

    result = prices[["asset", "observed_at", "adjusted_close"]].reset_index(drop=True).copy()
    result["position_after"] = target_exposure.to_numpy(dtype=float)
    result["position_before"] = result["position_after"].shift(1, fill_value=0)
    result["asset_return"] = result["adjusted_close"].pct_change(fill_method=None).fillna(0)
    result["gross_return"] = result["position_before"] * result["asset_return"]
    result["turnover"] = (result["position_after"] - result["position_before"]).abs()
    result["cost_fraction"] = result["turnover"] * (cost_bps / 10000)
    net_factor = (1 + result["gross_return"]) * (1 - result["cost_fraction"])
    result["net_return"] = net_factor - 1
    result["gross_capital"] = (1 + result["gross_return"]).cumprod()
    result["net_capital"] = net_factor.cumprod()
    previous_capital = result["net_capital"].shift(1, fill_value=1)
    result["cost_amount"] = previous_capital * (1 + result["gross_return"]) * result["cost_fraction"]
    result["drawdown"] = result["net_capital"] / result["net_capital"].cummax().clip(lower=1) - 1
    numeric = result.select_dtypes(include="number")
    if (not numeric.map(math.isfinite).all().all()
            or result[["gross_capital", "net_capital"]].le(0).any().any()):
        raise ValueError("La simulación ha generado capital no positivo o valores no finitos")
    return result
