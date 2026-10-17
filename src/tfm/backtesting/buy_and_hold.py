"""Generación de posiciones del benchmark, separada del motor financiero."""

import pandas as pd

from tfm.backtesting.engine import simulate_long_cash


def simulate_buy_and_hold(prices: pd.DataFrame, *, cost_bps: float) -> pd.DataFrame:
    """Decidir en la primera sesión y comprar al cierre de la segunda.

    La primera ganancia corresponde al intervalo segunda-tercera sesión. El
    intervalo recibido ya está seleccionado; no se interpreta historia anterior
    como una posición adquirida antes de empezar la simulación.
    """
    if len(prices) < 3:
        raise ValueError("Comprar y mantener requiere al menos tres sesiones en el intervalo")
    positions = pd.Series(1.0, index=prices.index)
    positions.iloc[0] = 0
    return simulate_long_cash(prices, positions, cost_bps=cost_bps)
