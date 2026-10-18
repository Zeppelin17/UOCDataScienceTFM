"""Respuestas incompatibles y errores de Yahoo, simulados sin red."""

import pandas as pd
import pytest

from tfm.sources import prices


@pytest.fixture
def frame():
    return pd.DataFrame({
        "Open": [100.0, 101.0], "High": [102.0, 103.0],
        "Low": [99.0, 100.0], "Close": [101.0, 102.0],
        "Adj Close": [100.0, 101.0], "Volume": [1000, 2000],
        "Dividends": [0.0, 1.0], "Stock Splits": [0.0, 0.0],
    }, index=pd.DatetimeIndex(["2020-12-30", "2020-12-31"], name="Date"))


PARAMETERS = {"tickers": "SPY", "start": "2020-12-30", "end": "2021-01-01"}


@pytest.mark.parametrize("bad", ["empty", "column", "holdout", "index", "dtype"])
def test_bad_response_is_rejected(monkeypatch, frame, bad):
    if bad == "empty":
        frame = pd.DataFrame()
    elif bad == "column":
        frame = frame.drop(columns="Adj Close")
    elif bad == "holdout":
        frame.index = pd.to_datetime(["2020-12-31", "2021-01-04"])
    elif bad == "index":
        frame.index = [0, 1]
    else:
        frame["Close"] = ["invalid", "invalid"]
    monkeypatch.setattr(prices.yf, "download", lambda **kwargs: frame)
    with pytest.raises(prices.DownloadError):
        prices.fetch_prices(PARAMETERS)


def test_network_failure_has_a_clear_error(monkeypatch):
    def failure(**kwargs):
        raise TimeoutError("provider timed out")
    monkeypatch.setattr(prices.yf, "download", failure)
    with pytest.raises(prices.DownloadError, match="La descarga de Yahoo ha fallado") as error:
        prices.fetch_prices(PARAMETERS)
    assert isinstance(error.value.__cause__, TimeoutError)
