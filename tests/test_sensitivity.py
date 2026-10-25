"""Sensibilidad prefijada: mismo simulador, efectos contables y flujo local."""

from pathlib import Path

import pandas as pd
import pytest

from tfm import cli, menu
from tfm.config import load_config
from tfm.data import (analyze_sensitivity, calculate_signals, prepare_shiller_data,
                      prepare_french_data, prepare_return_components, read_result)
from tfm.sensitivity import run_sensitivities, sensitivity_scenarios
from tfm.simulation import simulate_baselines, summarize_baselines
from tfm.sources.shiller import XLS_SIGNATURE
from test_shiller import workbook
from test_return_components import french_zip
from test_simulation import inputs
from test_menu import answer_with


PARAMETERS = {"initial_capital": 100.0, "transaction_cost_rate": 0.001,
              "annual_borrow_rate": 0.01, "include_dividends": True}


def test_prefixed_scenarios_reuse_the_engine_and_change_only_one_assumption():
    components, signals = inputs([0.01, -0.02, 0.015], dividends=[0.002] * 3,
                                 rf=[0.001] * 3, momentum=[1, 0, 1], reversal=[-1, 1, -1])
    original_components, original_signals = components.copy(deep=True), signals.copy(deep=True)
    scenarios = sensitivity_scenarios(PARAMETERS)
    assert len(scenarios) == 7
    result = run_sensitivities(components, signals, PARAMETERS)
    assert len(result) == 21 and result.months.eq(3).all()
    for scenario in scenarios:
        changed = [key for key in PARAMETERS if PARAMETERS[key] != scenario["parameters"][key]]
        assert changed == ([] if scenario["scenario"] == "central" else [scenario["changed_assumption"]])
        expected = summarize_baselines(simulate_baselines(components, signals, scenario["parameters"]), scenario["parameters"])
        actual = result.loc[result.scenario.eq(scenario["scenario"])]
        for row, summary in zip(actual.to_dict("records"), expected):
            assert row["strategy"] == summary["strategy"]
            assert row["capital_final"] == pytest.approx(summary["capital_final"])
            assert row["annualized_return"] == pytest.approx(summary["annualized_return"])
    assert result.loc[result.scenario.eq("central"), "annualized_return_delta"].eq(0).all()
    pd.testing.assert_frame_equal(components, original_components)
    pd.testing.assert_frame_equal(signals, original_signals)
    custom = {**PARAMETERS, "transaction_cost_rate": 0.002, "annual_borrow_rate": 0.02, "include_dividends": False}
    alternative = sensitivity_scenarios(custom)
    assert len(alternative) == 9 and alternative[0]["parameters"] == custom
    assert alternative[-1]["parameters"]["include_dividends"] is True


def test_borrow_and_dividend_effects_and_no_silent_omission_of_insolvency():
    components, signals = inputs([0.0, 0.0], dividends=[0.01, 0.01], rf=[0.001, 0.001], momentum=[0, 0])
    result = run_sensitivities(components, signals, PARAMETERS)
    for strategy in ("buy_and_hold", "momentum"):
        cases = result.loc[result.strategy.eq(strategy) & result.changed_assumption.isin(["none", "annual_borrow_rate"])]
        assert cases.capital_final.nunique() == 1  # No se cobra préstamo si no hay cortos.
    central = result.loc[result.scenario.eq("central")].set_index("strategy")
    no_dividend = result.loc[result.scenario.eq("dividends_toggle")].set_index("strategy")
    assert no_dividend.loc["buy_and_hold", "capital_final"] < central.loc["buy_and_hold", "capital_final"]
    assert no_dividend.loc["reversal", "capital_final"] > central.loc["reversal", "capital_final"]
    assert no_dividend.loc["momentum", "capital_final"] == central.loc["momentum", "capital_final"]
    components, signals = inputs([0.998])
    zero = {**PARAMETERS, "transaction_cost_rate": 0.0, "annual_borrow_rate": 0.0}
    with pytest.raises(ValueError, match="Negociación.*insolvente.*No se han omitido"):
        run_sensitivities(components, signals, zero)


def test_cli_menu_publication_and_upstream_invalidations(tmp_path, monkeypatch, capsys):
    configs = tmp_path / "configs"; configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    assert cli.main(["analyze-sensitivity", "--config", str(config)]) == 1
    assert "Faltan" in capsys.readouterr().err
    workbook(monkeypatch)
    shiller = tmp_path / "shiller.xls"; shiller.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "french.zip"
    french.write_bytes(french_zip([f"{m.replace('-', '')},unused,unused,unused,0.2"
                                   for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepare_shiller_data(config, file=shiller); prepare_french_data(config, file=french)
    calculate_signals(config); prepare_return_components(config)
    assert cli.main(["analyze-sensitivity", "--config", str(config)]) == 0
    table, report = read_result(load_config(config), "baseline_sensitivity")
    assert len(table) == 21 and table.months.eq(756).all()
    assert report["first_period"] == "1927-01" and report["last_period"] == "1989-12"
    assert len(report["comparisons"]) == 21
    output = capsys.readouterr().out
    assert "7 escenarios" in output and "puntos porcentuales" in output
    assert "sin evaluación desde 1990" in output
    monkeypatch.setattr(menu, "_clear_screen", lambda: None)
    answer_with(monkeypatch, ["9", "", "3", "7", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    assert "Primeras cinco filas" in capsys.readouterr().out
    before = config.read_bytes()
    config.write_text(config.read_text().replace("annual_borrow_rate = 0.01", "annual_borrow_rate = 0.02"))
    with pytest.raises(ValueError, match="configuración"):
        read_result(load_config(config), "baseline_sensitivity")
    config.write_bytes(before)
    path = tmp_path / "data/processed/baseline_sensitivity.parquet"
    saved = (path.read_bytes(), path.with_suffix(".json").read_bytes())
    def fail(*args):
        raise ValueError("Escenario insolvente")
    with monkeypatch.context() as patch:
        patch.setattr("tfm.data.run_sensitivities", fail)
        with pytest.raises(ValueError, match="insolvente"):
            analyze_sensitivity(config)
    assert saved == (path.read_bytes(), path.with_suffix(".json").read_bytes())
    for regenerate in (calculate_signals, prepare_return_components, prepare_french_data, prepare_shiller_data):
        # Reutilizar la salida ya comprobada para verificar cada invalidación sin repetir las simulaciones.
        path.write_bytes(saved[0]); path.with_suffix(".json").write_bytes(saved[1])
        regenerate(config)
        assert not path.exists() and not path.with_suffix(".json").exists()
