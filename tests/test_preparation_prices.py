from hashlib import sha256
import json

import pandas as pd
import pytest

from tfm.preparation.prices import PriceQualityError, prepare_prices


def snapshot(tmp_path, *, duplicate=False, missing=False):
    directory = tmp_path / "raw"
    directory.mkdir()
    frame = pd.DataFrame({
        "Open": [102.0, 100.0], "High": [104.0, 102.0],
        "Low": [101.0, 99.0], "Close": [103.0, 101.0],
        "Adj Close": [102.0, 100.0], "Volume": [2000, 1000],
        "Dividends": [1.0, 0.0], "Stock Splits": [0.0, 0.0],
    }, index=pd.to_datetime(["2020-12-31", "2020-12-30"]))
    if duplicate:
        frame.index = pd.to_datetime(["2020-12-31", "2020-12-31"])
    if missing:
        frame.iloc[0, frame.columns.get_loc("Close")] = float("nan")
    data = directory / "prices.parquet"
    frame.to_parquet(data)
    manifest = {"schema_version": 1, "provider": "yahoo", "instrument": "SPY",
                "snapshot_id": "test", "data_file": "prices.parquet", "rows": 2,
                "sha256": sha256(data.read_bytes()).hexdigest(),
                "parameters": {"start": "2020-12-30", "end": "2021-01-01"}}
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory, frame


def test_prepared_prices_preserve_values_and_provenance(tmp_path):
    raw, original = snapshot(tmp_path)
    output = prepare_prices(raw, tmp_path / "processed")
    table = pd.read_parquet(output / "prices.parquet")
    assert table["observed_at"].is_monotonic_increasing
    assert table["close"].tolist() == [101.0, 103.0]
    assert table["adjusted_close"].tolist() == [100.0, 102.0]
    assert table["dividends"].tolist() == [0.0, 1.0]
    assert table["asset"].tolist() == ["SPY", "SPY"]
    pd.testing.assert_frame_equal(pd.read_parquet(raw / "prices.parquet"), original)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["source_snapshot_id"] == "test"
    assert manifest["sha256"] == sha256((output / "prices.parquet").read_bytes()).hexdigest()
    assert manifest["status"] == "passed"
    assert prepare_prices(raw, tmp_path / "processed") != output


def test_duplicates_and_missing_values_block_publication(tmp_path):
    raw, _ = snapshot(tmp_path, duplicate=True, missing=True)
    with pytest.raises(PriceQualityError) as error:
        prepare_prices(raw, tmp_path / "processed")
    report = json.loads(error.value.report_path.read_text())
    assert report["status"] == "failed"
    assert report["error_counts"]["duplicate_sessions"] == 1
    assert report["missing_by_column"]["close"] == 1
    assert not (error.value.report_path.parent / "prices.parquet").exists()


def test_modified_snapshot_is_rejected_before_preparation(tmp_path):
    raw, frame = snapshot(tmp_path)
    frame["Close"] = 999.0
    frame.to_parquet(raw / "prices.parquet")
    with pytest.raises(PriceQualityError, match="SHA-256"):
        prepare_prices(raw, tmp_path / "processed")
    assert not (tmp_path / "processed").exists()
