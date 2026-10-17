"""Auditoría diaria contra XNYS, calendario de referencia de sesiones de renta variable US."""

from importlib.metadata import version

import exchange_calendars as xcals
import pandas as pd

from tfm.backtesting.engine import validate_prices


METHOD_VERSION = 1
CALENDAR_NAME = "XNYS"


def audit_calendar(prices: pd.DataFrame, start: str, end_exclusive: str, *, calendar_name: str) -> tuple[dict, pd.DataFrame]:
    """Comparar todo [start, end_exclusive), incluidos extremos sin cotización.

    XNYS se usa como referencia explícita de sesiones diarias US, no como
    reconstrucción del mercado primario histórico de SPY o de sus cotizaciones.
    Los cierres reducidos cuentan como sesiones; no se auditan precios intradía.
    """
    validate_prices(prices)
    start, end = pd.Timestamp(start), pd.Timestamp(end_exclusive)
    if (start.tz is not None or end.tz is not None or start != start.normalize()
            or end != end.normalize() or start >= end or pd.isna(start) or pd.isna(end)):
        raise ValueError("Intervalo de calendario inválido: se requieren fechas y fin exclusivo")
    if calendar_name != CALENDAR_NAME:
        raise ValueError("Solo se ha documentado XNYS como calendario de referencia diario de SPY")
    # Ampliar límites para admitir festivos/fines de semana en los extremos.
    calendar = xcals.get_calendar(calendar_name, start=start - pd.Timedelta(days=7), end=end + pd.Timedelta(days=7))
    expected = calendar.sessions_in_range(start, end - pd.Timedelta(days=1))
    observed = pd.DatetimeIndex(prices["observed_at"])
    missing, unexpected = expected.difference(observed), observed.difference(expected)
    schedule = calendar.schedule.loc[expected, ["open", "close"]].copy()
    schedule.insert(0, "session", expected)
    schedule["early_close"] = expected.isin(calendar.early_closes)
    schedule = schedule.reset_index(drop=True)
    result = {
        "status": "failed" if len(missing) or len(unexpected) else "passed",
        "calendar_name": calendar_name, "library": "exchange_calendars",
        "library_version": version("exchange-calendars"), "tzdata_version": version("tzdata"),
        "expected_sessions": len(expected), "observed_sessions": len(observed),
        "missing_sessions": missing.strftime("%Y-%m-%d").tolist(),
        "unexpected_sessions": unexpected.strftime("%Y-%m-%d").tolist(),
        "early_close_sessions": int(schedule["early_close"].sum()),
        "scope": "Sesiones diarias en el intervalo solicitado; no exactitud de precios ni horario intradía.",
    }
    return result, schedule
