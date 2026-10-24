"""Recorridos esenciales del menú guiado, sin red ni archivos del usuario."""

from pathlib import Path

import pandas as pd
import pytest

from tfm import cli, menu
from tfm.data import prepare_shiller_data, calculate_signals
from tfm.sources.shiller import XLS_SIGNATURE
from test_shiller import workbook


@pytest.fixture
def study(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    original = tmp_path / "data/raw/shiller/SHILLER_SP_COMPOSITE/old_identifier/original.xls"
    original.parent.mkdir(parents=True)
    original.write_bytes(XLS_SIGNATURE + b"synthetic workbook")
    workbook(monkeypatch)
    monkeypatch.setattr(menu, "_clear_screen", lambda: None)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No debe descargar Shiller"))
    return config, original


def answer_with(monkeypatch, values):
    answers = iter(values)
    prompts = []
    def answer(prompt):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr("builtins.input", answer)
    return prompts


def test_guided_shiller_flow_reuses_history_and_explains_signals(study, monkeypatch, capsys):
    config, original = study
    before = original.read_bytes()
    answer_with(monkeypatch, ["1", "3", "1", "", "2", "", "3", "2", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    root = config.parent.parent
    signals = pd.read_parquet(root / "data/processed/shiller_signals.parquet")
    assert len(signals) == 756 and signals.both_rules_available.sum() == 756
    assert original.read_bytes() == before
    assert (root / "data/raw/shiller.xls").read_bytes() == before
    assert not (root / "outputs").exists()
    output = capsys.readouterr().out
    assert "Estudio actual: Shiller mensual" in output
    assert "Originales anteriores de Shiller" in output and "old_identifier" not in output
    assert "Meses con ambas señales disponibles: 756" in output
    assert "1927-01" in output and "Primeras cinco filas" in output
    assert "sin simulación de rentabilidades" in output
    assert "Finder" not in output and "Registro de ejecución" not in output


def test_missing_inputs_and_cancelled_imports_return_without_extra_pauses(study, monkeypatch, capsys):
    config, _ = study
    prompts = answer_with(monkeypatch, ["99", "", "2", "", "1", "0", "1", "2", "missing.xls", "0", "3", "0", "5", "", "0"])
    assert menu.interactive_menu(config) == 0
    assert sum("Pulsa Intro" in p for p in prompts) == 2
    assert not (config.parent.parent / "data/processed").exists()
    output = capsys.readouterr().out
    assert "usa la opción 1 antes de calcular señales" in output
    assert "No se encuentra ese archivo" in output
    assert "1. Preparar datos de Shiller; después 2. Calcular señales" in output
    assert "Faltan los datos de SPY o su resumen" in output
    assert "Configuración del estudio" in output and "evaluación deshabilitada" in output


def test_spy_download_is_explicit_and_separate(study, monkeypatch, capsys):
    config, _ = study
    calls = []
    frame = pd.DataFrame({"Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.0],
                          "Adj Close": [100.0], "Volume": [1000], "Dividends": [0.0], "Stock Splits": [0.0]},
                         index=pd.DatetimeIndex(["2020-12-30"], name="Date"))
    def download(**parameters):
        calls.append(parameters)
        return frame
    monkeypatch.setattr("tfm.sources.prices.yf.download", download)
    answer_with(monkeypatch, ["4", "0", "4", "1", "", "3", "3", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    assert len(calls) == 1 and calls[0]["tickers"] == "SPY" and calls[0]["auto_adjust"] is False
    assert not (config.parent.parent / "data/processed/shiller_monthly.parquet").exists()
    output = capsys.readouterr().out
    assert "Yahoo Finance mediante yfinance" in output
    assert "2021-01-01 (fin exclusivo)" in output
    assert "SPY se mantiene separado de Shiller" in output
    assert "Cierre ajustado" in output


def test_consultation_and_status_are_read_only_and_reject_old_configuration(study, monkeypatch, capsys):
    config, original = study
    root = config.parent.parent
    prepare_shiller_data(config, file=original)
    calculate_signals(config)
    before = {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}
    answer_with(monkeypatch, ["3", "1", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    assert cli.main(["status", "--config", str(config)]) == 0
    assert "disponible para consultar (756 filas)" in capsys.readouterr().out
    config.write_text(config.read_text().replace('history_start = "1925-12"', 'history_start = "1925-01"'))
    answer_with(monkeypatch, ["3", "2", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    output = capsys.readouterr().out
    assert "periodos han cambiado" in output and "No se puede consultar" in output
    assert "Primeras cinco filas" not in output
    assert before == {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}


def test_terminal_entry_and_recovery_from_configuration_or_closed_input(study, monkeypatch, capsys):
    config, _ = study
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main([]) == 0
    assert "prepare-data" in capsys.readouterr().out
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    calls = []
    monkeypatch.setattr(cli, "interactive_menu", lambda: calls.append(True) or 0)
    assert cli.main([]) == 0 and calls == [True]
    saved = config.read_bytes()
    config.write_text("invalid toml")
    answers = iter(["1", "0"])
    def fix_configuration(prompt):
        config.write_bytes(saved)
        return next(answers)
    monkeypatch.setattr("builtins.input", fix_configuration)
    assert menu.interactive_menu(config) == 0
    assert "No se puede leer la configuración" in capsys.readouterr().out
    answers = iter([KeyboardInterrupt(), "", EOFError()])
    def interrupt_or_close(prompt):
        value = next(answers)
        if isinstance(value, Exception) or isinstance(value, KeyboardInterrupt):
            raise value
        return value
    monkeypatch.setattr("builtins.input", interrupt_or_close)
    assert menu.interactive_menu(config) == 0
    output = capsys.readouterr().out
    assert "Operación cancelada" in output and "Menú cerrado" in output
