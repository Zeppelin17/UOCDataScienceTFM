"""Normalización y comprobaciones estructurales de los datos diarios de SPY."""

import pandas as pd


COLUMN_NAMES = {
    "Open": "open", "High": "high", "Low": "low", "Close": "close",
    "Adj Close": "adjusted_close", "Volume": "volume",
    "Dividends": "dividends", "Stock Splits": "stock_splits",
}


class PriceQualityError(ValueError):
    """El original no tiene una estructura de precios diarios compatible."""

def normalize_prices(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cambiar nombres y ordenar sesiones sin imputar ni eliminar filas.

    Devuelve la tabla y un informe. Los errores del informe bloquean su
    publicación; los errores de estructura impiden incluso normalizarla.
    """
    if isinstance(frame.columns, pd.MultiIndex) or not frame.columns.is_unique:
        raise PriceQualityError("Se esperaban columnas simples y únicas")
    if not set(COLUMN_NAMES).issubset(frame.columns):
        raise PriceQualityError("Faltan campos de precios o eventos")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is not None:
        raise PriceQualityError("Se esperaban fechas de sesión sin zona horaria")
    for column in COLUMN_NAMES:
        dtype = frame[column].dtype
        if not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
            raise PriceQualityError(f"Campo no numérico: {column}")
    table = frame[list(COLUMN_NAMES)].rename(columns=COLUMN_NAMES).copy()
    table.insert(0, "observed_at", frame.index)
    table.insert(0, "asset", "SPY")
    table["source"] = "yahoo"
    table = table.sort_values("observed_at", kind="stable").reset_index(drop=True)
    numeric = table[list(COLUMN_NAMES.values())]
    prices = table[["open", "high", "low", "close", "adjusted_close"]]
    bad_ohlc = (
        (table["low"] > table["high"])
        | (table["open"] < table["low"]) | (table["open"] > table["high"])
        | (table["close"] < table["low"]) | (table["close"] > table["high"])
    )
    counts = {
        "empty": int(table.empty),
        "missing_dates": int(table["observed_at"].isna().sum()),
        "duplicate_sessions": int(table.duplicated(["asset", "observed_at"]).sum()),
        "non_daily_dates": int((table["observed_at"] != table["observed_at"].dt.normalize()).sum()),
        "non_finite_values": int((numeric.isna() | numeric.isin([float("inf"), float("-inf")])).sum().sum()),
        "non_positive_prices": int((prices <= 0).sum().sum()),
        "negative_volume": int((table["volume"] < 0).sum()),
        "negative_dividends": int((table["dividends"] < 0).sum()),
        "negative_stock_splits": int((table["stock_splits"] < 0).sum()),
        "inconsistent_ohlc": int(bad_ohlc.sum()),
    }
    report = {
        "status": "failed" if any(counts.values()) else "passed",
        "rows": len(table), "error_counts": counts,
        "missing_by_column": {key: int(value) for key, value in numeric.isna().sum().items()},
        "first_session": table["observed_at"].min().isoformat() if table["observed_at"].notna().any() else None,
        "last_session": table["observed_at"].max().isoformat() if table["observed_at"].notna().any() else None,
        "input_was_sorted": frame.index.is_monotonic_increasing,
        "warnings": [],
    }
    return table, report
