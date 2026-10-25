"""Escalado causal, cuentas parciales y comparación conjunta sin red."""

from pathlib import Path
from statistics import stdev
import math

import pandas as pd
import pytest

from tfm import cli, menu
from tfm.config import load_config
from tfm.data import (prepare_shiller_data, prepare_french_data, calculate_signals,
                      prepare_return_components, read_result, compare_simple_strategies)
from tfm.simulation import simulate_baselines
from tfm.volatility import build_volatility_scale, validate_volatility_parameters
from tfm.sources.shiller import INSTRUMENT, XLS_SIGNATURE
from test_shiller import workbook
from test_return_components import french_zip
from test_simulation import inputs, PARAMETERS
from test_menu import answer_with


RISK = {"lookback_months": 12, "target_annual_volatility": 0.12, "max_exposure": 1.0}


def test_fractional_long_short_cash_rebalancing_and_original_accounts():
    components, signals = inputs([0.1], dividends=[0.02], rf=[0.003])
    scale = pd.Series([0.5], index=components.period)
    result = simulate_baselines(components, signals, PARAMETERS, exposure_scale=scale).set_index("strategy")
    invested = 100 / 1.005
    long = result.loc["buy_and_hold"]
    assert long.position == 0.5 and long.cash_interest == pytest.approx(invested * 0.5 * 0.003)
    assert long.capital_end == pytest.approx(invested * (1 + 0.5 * 0.12 + 0.5 * 0.003 - 0.01 * 0.5 * 1.12))
    short = result.loc["reversal"]
    assert short.position == -0.5 and short.cash_interest == pytest.approx(invested * 0.003)
    assert short.borrow_cost == pytest.approx(invested * 0.5 * 0.12 / 12)
    assert short.dividend_pnl == pytest.approx(-invested * 0.5 * 0.02)
    assert short.capital_end == pytest.approx(invested * (1 - 0.5 * 0.12 + 0.003 - 0.005 - 0.01 * 0.5 * 1.1))
    assert result.asset_notional_end.eq(0).all()
    one = pd.Series([1.0], index=components.period)
    pd.testing.assert_frame_equal(simulate_baselines(components, signals, PARAMETERS),
                                  simulate_baselines(components, signals, PARAMETERS, exposure_scale=one),
                                  check_dtype=False, check_exact=True)
    with pytest.raises(ValueError, match="mismo orden"):
        simulate_baselines(components, signals, PARAMETERS, exposure_scale=pd.Series([0.5], index=["1927-02"]))
    components, signals = inputs([0.0, 0.0], reversal=[1, 1])
    scale = pd.Series([1.0, 0.5], index=components.period)
    rows = simulate_baselines(components, signals, PARAMETERS, exposure_scale=scale).query("strategy == 'buy_and_hold'").reset_index(drop=True)
    assert rows.loc[1, "trade_notional"] == pytest.approx(0.5 * rows.loc[1, "capital_start"] / 0.995)
    assert rows.loc[1, "transaction_cost"] > 0


def test_risk_window_is_prior_only_with_explicit_cap_zero_risk_and_missing_history():
    changes = [0.02, -0.01] * 14
    prices = [100.0]
    for change in changes:
        prices.append(prices[-1] * (1 + change))
    monthly = pd.DataFrame({"asset": INSTRUMENT, "period": pd.period_range("1924-12", periods=len(prices), freq="M").astype(str),
                            "price_monthly_mean": prices, "dividend_annualized": [object() for _ in prices]})
    _, signals = inputs([0.01, -0.02, 0.01])
    low_target = {**RISK, "target_annual_volatility": 0.01}
    result = build_volatility_scale(monthly, signals, low_target)
    expected = stdev(changes[12:24]) * math.sqrt(12)
    assert result.loc[0, "estimated_annual_volatility"] == pytest.approx(expected)
    assert result.loc[0, "volatility_scale"] == pytest.approx(0.01 / expected)
    assert result.loc[0, "volatility_price_start_period"] == "1925-12"
    changed = monthly.copy(); changed.loc[25:, "price_monthly_mean"] = 1.0
    pd.testing.assert_frame_equal(build_volatility_scale(changed, signals, low_target).iloc[:1], result.iloc[:1])
    flat = monthly.copy(); flat["price_monthly_mean"] = 100.0
    assert build_volatility_scale(flat, signals, RISK).volatility_scale.eq(1).all()
    assert build_volatility_scale(monthly, signals, RISK).volatility_scale.eq(1).all()
    with pytest.raises(ValueError, match="Falta historia"):
        build_volatility_scale(monthly, signals, {**RISK, "lookback_months": 25})
    with pytest.raises(ValueError, match="apalancamiento"):
        validate_volatility_parameters({**RISK, "max_exposure": 1.5})


def test_cli_menu_joint_comparison_configuration_and_invalidations(tmp_path, monkeypatch, capsys):
    configs = tmp_path / "configs"; configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    assert cli.main(["compare-simple-strategies", "--config", str(config)]) == 1
    assert "Faltan" in capsys.readouterr().err
    workbook(monkeypatch)
    shiller = tmp_path / "shiller.xls"; shiller.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "french.zip"
    french.write_bytes(french_zip([f"{m.replace('-', '')},unused,unused,unused,0.2"
                                   for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepare_shiller_data(config, file=shiller); prepare_french_data(config, file=french)
    calculate_signals(config); prepare_return_components(config)
    before = {p: p.read_bytes() for p in (tmp_path / "data").rglob("*") if p.is_file()}
    assert cli.main(["compare-simple-strategies", "--config", str(config)]) == 0
    assert all(p.read_bytes() == content for p, content in before.items())
    table, report = read_result(load_config(config), "simple_comparisons")
    assert len(table) == 6048 and report["months_per_strategy"] == 756
    assert report["first_period"] == "1927-01" and report["last_period"] == "1989-12"
    assert len(report["strategies"]) == 8 and table.position.between(-1, 1).all()
    assert table.estimated_annual_volatility.eq(0).all() and table.volatility_scale.eq(1).all()
    output = capsys.readouterr().out
    assert "ocho cuentas" in output and "Modelos y evaluación desde 1990 siguen pendientes" in output
    monkeypatch.setattr(menu, "_clear_screen", lambda: None)
    answer_with(monkeypatch, ["11", "", "3", "9", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    assert "Primeras cinco filas" in capsys.readouterr().out
    previous = config.read_bytes()
    config.write_text(config.read_text().replace("target_annual_volatility = 0.12", "target_annual_volatility = 0.10"))
    with pytest.raises(ValueError, match="configuración"):
        read_result(load_config(config), "simple_comparisons")
    # Cambiar el comparador no obliga a preparar las fuentes otra vez.
    read_result(load_config(config), "monthly_return_components")
    config.write_bytes(previous)
    path = tmp_path / "data/processed/simple_comparisons.parquet"
    saved = path.read_bytes(), path.with_suffix(".json").read_bytes()
    for regenerate in (calculate_signals, prepare_return_components, prepare_french_data, prepare_shiller_data):
        path.write_bytes(saved[0]); path.with_suffix(".json").write_bytes(saved[1])
        regenerate(config)
        assert not path.exists() and not path.with_suffix(".json").exists()
