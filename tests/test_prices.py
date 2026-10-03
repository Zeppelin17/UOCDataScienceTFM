from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest

from tfm.sources import prices


@pytest.fixture
def config_path(tmp_path):
    directory = tmp_path / "configs"
    directory.mkdir()
    path = directory / "data.toml"
    path.write_text((Path(__file__).parents[1] / "configs/data.toml").read_text())
    return path


@pytest.fixture
def frame():
    return pd.DataFrame({
        "Open": [100.0, 101.0], "High": [102.0, 103.0],
        "Low": [99.0, 100.0], "Close": [101.0, 102.0],
        "Adj Close": [100.0, 101.0], "Volume": [1000, 2000],
        "Dividends": [0.0, 1.0], "Stock Splits": [0.0, 0.0],
    }, index=pd.DatetimeIndex(["2020-12-30", "2020-12-31"], name="Date"))


def test_snapshot_roundtrip_provenance_and_no_overwrite(monkeypatch, config_path, frame):
    calls = []
    def download(**kwargs):
        calls.append(kwargs)
        return frame
    monkeypatch.setattr(prices.yf, "download", download)
    first = prices.download_prices(config_path)
    second = prices.download_prices(config_path)
    assert first != second
    pd.testing.assert_frame_equal(pd.read_parquet(first / "prices.parquet"), frame)
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["sha256"] == sha256((first / "prices.parquet").read_bytes()).hexdigest()
    assert manifest["parameters"] == calls[0]
    assert calls[0]["end"] == "2021-01-01"
    assert calls[0]["auto_adjust"] is False
    assert manifest["rows"] == 2
    assert first.parent == config_path.parent.parent / "data/raw/yahoo/SPY"


@pytest.mark.parametrize("bad", ["empty", "column", "holdout", "index", "dtype"])
def test_bad_response_creates_no_snapshot(monkeypatch, config_path, frame, bad):
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
        prices.download_prices(config_path)
    assert not (config_path.parent.parent / "data/raw").exists()


def test_network_failure_is_explicit(monkeypatch, config_path):
    def failure(**kwargs):
        raise TimeoutError("provider timed out")
    monkeypatch.setattr(prices.yf, "download", failure)
    with pytest.raises(prices.DownloadError) as error:
        prices.download_prices(config_path)
    assert isinstance(error.value.__cause__, TimeoutError)


def test_invalid_config_never_downloads(monkeypatch, config_path):
    config_path.write_text(config_path.read_text().replace("auto_adjust = false", "auto_adjust = true"))
    def unexpected(**kwargs):
        pytest.fail("No debe contactar con Yahoo")
    monkeypatch.setattr(prices.yf, "download", unexpected)
    with pytest.raises(ValueError):
        prices.download_prices(config_path)


def test_write_failure_removes_partial_snapshot(monkeypatch, config_path, frame):
    monkeypatch.setattr(prices.yf, "download", lambda **kwargs: frame)
    def failure(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", failure)
    with pytest.raises(OSError):
        prices.download_prices(config_path)
    assert not list((config_path.parent.parent / "data/raw").rglob("manifest.json"))
    assert list((config_path.parent.parent / "data/raw/yahoo/SPY").iterdir()) == []
