"""Conservación de precios y detección de errores estructurales de SPY."""

import pandas as pd

from tfm.preparation.prices import normalize_prices


def original_prices():
    return pd.DataFrame({
        "Open": [102.0, 100.0], "High": [104.0, 102.0],
        "Low": [101.0, 99.0], "Close": [103.0, 101.0],
        "Adj Close": [102.0, 100.0], "Volume": [2000, 1000],
        "Dividends": [1.0, 0.0], "Stock Splits": [0.0, 0.0],
    }, index=pd.to_datetime(["2020-12-31", "2020-12-30"]))


def test_normalization_preserves_prices_and_events():
    original = original_prices()
    before = original.copy(deep=True)
    table, report = normalize_prices(original)
    assert report["status"] == "passed"
    assert table["observed_at"].is_monotonic_increasing
    assert table["close"].tolist() == [101.0, 103.0]
    assert table["adjusted_close"].tolist() == [100.0, 102.0]
    assert table["dividends"].tolist() == [0.0, 1.0]
    assert table["asset"].tolist() == ["SPY", "SPY"]
    pd.testing.assert_frame_equal(original, before)


def test_duplicates_and_missing_values_are_reported_without_correction():
    frame = original_prices()
    frame.index = pd.to_datetime(["2020-12-31", "2020-12-31"])
    frame.iloc[0, frame.columns.get_loc("Close")] = float("nan")
    table, report = normalize_prices(frame)
    assert len(table) == 2 and table.close.isna().sum() == 1
    assert report["status"] == "failed"
    assert report["error_counts"]["duplicate_sessions"] == 1
    assert report["missing_by_column"]["close"] == 1
