"""Obtención de precios diarios de SPY mediante Yahoo Finance."""

import pandas as pd
import yfinance as yf


REQUIRED_COLUMNS = {
    "Open", "High", "Low", "Close", "Adj Close", "Volume",
    "Dividends", "Stock Splits",
}

class DownloadError(RuntimeError):
    """El proveedor no devolvió una respuesta utilizable."""



def fetch_prices(parameters: dict) -> pd.DataFrame:
    """Obtener precios de Yahoo sin persistir snapshots ni registros."""
    start, end = parameters["start"], parameters["end"]
    try:
        frame = yf.download(**parameters)
    except Exception as exc:
        raise DownloadError("La descarga de Yahoo ha fallado") from exc
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise DownloadError("Yahoo no devolvió precios; no se han guardado datos")
    if isinstance(frame.columns, pd.MultiIndex) or not REQUIRED_COLUMNS.issubset(frame.columns):
        raise DownloadError("La respuesta no contiene las columnas de precios y eventos esperadas")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans or frame.index.tz is not None:
        raise DownloadError("Se esperaba un índice de fechas de sesión sin zona horaria")
    if (frame.index < pd.Timestamp(start)).any() or (frame.index >= pd.Timestamp(end)).any():
        raise DownloadError("La respuesta contiene fechas fuera del periodo solicitado")
    if any(not pd.api.types.is_numeric_dtype(frame[column]) for column in REQUIRED_COLUMNS):
        raise DownloadError("La respuesta contiene campos financieros no numéricos")
    return frame
