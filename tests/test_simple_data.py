"""Regresiones del flujo simplificado: mismas tablas, sin runs ni huellas."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tfm import cli
from tfm.config import load_config
from tfm.data import calculate_signals, load_monthly, prepare_shiller_data, prepare_spy_data
from tfm.preparation.shiller import normalize_shiller
from tfm.signals.shiller import build_price_signals
from tfm.sources import prices
from tfm.sources.shiller import XLS_SIGNATURE
from test_shiller import workbook


@pytest.fixture
def study(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    original = tmp_path / "original.xls"
    original.write_bytes(XLS_SIGNATURE + b"synthetic workbook")
    workbook(monkeypatch)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    return config, original


def test_offline_cli_has_identical_data_signals_and_stable_paths(study, capsys):
    config, original = study
    root = config.parent.parent
    assert cli.main(["prepare-data", "--config", str(config), "--file", str(original)]) == 0
    assert cli.main(["calculate-signals", "--config", str(config)]) == 0
    settings = load_config(config)
    expected, _ = normalize_shiller(original.read_bytes(), history_start="1926-01", policy_bytes=config.read_bytes())
    pd.testing.assert_frame_equal(load_monthly(settings), expected)
    result = pd.read_parquet(root / "data/processed/shiller_signals.parquet")
    expected_signals = build_price_signals(expected)
    expected_signals = expected_signals.loc[expected_signals.target_period.between("1927-01", "1989-12")].reset_index(drop=True)
    pd.testing.assert_frame_equal(result, expected_signals)
    assert len(expected) == 768 and len(result) == 756 and result.both_rules_available.sum() == 755
    assert (root / "data/raw/shiller.xls").read_bytes() == original.read_bytes()
    source = json.loads((root / "data/raw/shiller_fuente.json").read_bytes())
    assert source["acquisition"]["method"] == "local_file_import"
    assert "sha256" not in source and not (root / "outputs").exists()
    assert not list((root / "data").rglob("*.csv"))
    files = {p.relative_to(root) for p in (root / "data").rglob("*") if p.is_file()}
    calculate_signals(config)
    assert files == {p.relative_to(root) for p in (root / "data").rglob("*") if p.is_file()}
    prepare_shiller_data(config)  # Reutiliza sin contactar con la fuente.
    assert not (root / "data/processed/shiller_signals.parquet").exists()
    assert not (root / "data/processed/shiller_signals.json").exists()
    output = capsys.readouterr().out
    assert "755" in output and "sin simulación" in output and "1927-01" in output


def test_bad_input_and_failed_write_keep_previous_valid_outputs(study, monkeypatch):
    config, original = study
    root = config.parent.parent
    prepare_shiller_data(config, file=original)
    calculate_signals(config)
    before = {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}
    workbook(monkeypatch, "duplicate")
    with pytest.raises(ValueError, match="duplicate_months"):
        prepare_shiller_data(config)
    workbook(monkeypatch)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda *a, **k: (_ for _ in ()).throw(OSError("disco lleno")))
    with pytest.raises(OSError, match="disco lleno"):
        prepare_shiller_data(config)
    assert before == {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}


def test_changed_periods_and_original_replacement_are_explicit(study):
    config, original = study
    prepare_shiller_data(config, file=original)
    config.write_text(config.read_text().replace('history_start = "1926-01"', 'history_start = "1925-01"'))
    with pytest.raises(ValueError, match="periodos han cambiado"):
        calculate_signals(config)
    with pytest.raises(ValueError, match="Ya existe el original"):
        prepare_shiller_data(config, file=original)
    config.write_text(config.read_text().replace('development_end = "1989-12-31"', 'development_end = "1990-12-31"'))
    with pytest.raises(ValueError, match="evaluación desde 1990"):
        load_config(config)


def test_spy_keeps_yahoo_options_and_reuses_its_original(study, monkeypatch, capsys):
    config, _ = study
    root = config.parent.parent
    frame = pd.DataFrame({"Open": [100.0, 101.0], "High": [102.0, 103.0],
                          "Low": [99.0, 100.0], "Close": [101.0, 102.0],
                          "Adj Close": [100.0, 101.0], "Volume": [1000, 2000],
                          "Dividends": [0.0, 1.0], "Stock Splits": [0.0, 0.0]},
                         index=pd.DatetimeIndex(["2020-12-30", "2020-12-31"], name="Date"))
    calls = []
    def failure(**parameters):
        raise TimeoutError("provider timed out")
    monkeypatch.setattr(prices.yf, "download", failure)
    assert cli.main(["prepare-data", "--source", "spy", "--config", str(config)]) == 1
    assert "La descarga de Yahoo ha fallado" in capsys.readouterr().err
    assert not (root / "data/raw/spy.parquet").exists()
    def download(**parameters):
        calls.append(parameters)
        return frame
    monkeypatch.setattr(prices.yf, "download", download)
    result = prepare_spy_data(config)
    first = pd.read_parquet(result["path"])
    again = prepare_spy_data(config)
    pd.testing.assert_frame_equal(first, pd.read_parquet(again["path"]))
    pd.testing.assert_frame_equal(frame, pd.read_parquet(root / "data/raw/spy.parquet"))
    assert len(calls) == 1 and calls[0]["end"] == "2021-01-01"
    assert calls[0]["auto_adjust"] is False and calls[0]["actions"] is True
    assert first.asset.eq("SPY").all() and first.source.eq("yahoo").all()
    assert not (root / "data/processed/shiller_monthly.parquet").exists()
