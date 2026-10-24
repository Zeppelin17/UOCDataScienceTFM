"""Cuenta mensual: signos, efectivo, costes, fechas y publicación del flujo."""

from pathlib import Path

import pandas as pd
import pytest

from tfm import cli
from tfm.config import load_config
from tfm.data import (calculate_signals, prepare_shiller_data, prepare_french_data,
                      prepare_return_components, simulate_basic_strategies, read_result)
from tfm.simulation import simulate_baselines, summarize_baselines
from tfm.sources.shiller import INSTRUMENT, XLS_SIGNATURE
from test_shiller import workbook
from test_return_components import french_zip


PARAMETERS = {"initial_capital": 100.0, "transaction_cost_rate": 0.01,
              "annual_borrow_rate": 0.12, "include_dividends": True}


def inputs(prices, *, dividends=None, rf=None, momentum=None, reversal=None):
    months = pd.period_range("1927-01", periods=len(prices), freq="M")
    components = pd.DataFrame({"asset": INSTRUMENT, "period": months.astype(str),
                               "previous_period": (months - 1).astype(str), "price_return": prices,
                               "dividend_return_approx": dividends if dividends is not None else 0.0,
                               "rf_return": rf if rf is not None else 0.0})
    signals = pd.DataFrame({"asset": INSTRUMENT, "basis": "monthly_mean_price",
                            "target_period": months.astype(str), "decision_period": (months - 1).astype(str),
                            "momentum_signal": momentum if momentum is not None else 1,
                            "reversal_signal": reversal if reversal is not None else -1})
    return components, signals


def test_manual_long_cash_short_and_terminal_costs():
    components, signals = inputs([0.1], dividends=[0.02], rf=[0.003], momentum=[0])
    result = simulate_baselines(components, signals, PARAMETERS).set_index("strategy")
    invested = 100 / 1.01
    long = result.loc["buy_and_hold"]
    assert long.capital_end == pytest.approx(invested * 1.12 * 0.99)
    assert long.cash_interest == 0 and long.borrow_cost == 0
    cash = result.loc["momentum"]
    assert cash.capital_end == pytest.approx(100.3)
    assert cash.trade_notional == 0 and cash.liquidation_cost == 0 and cash.borrow_cost == 0
    short = result.loc["reversal"]
    assert short.capital_end == pytest.approx(invested * (1 + 0.003 - 0.1 - 0.02 - 0.01) - 0.01 * invested * 1.1)
    assert short.dividend_pnl == pytest.approx(-invested * 0.02)
    assert short.cash_interest == pytest.approx(invested * 0.003)  # No interés doble del ingreso de la venta.
    assert short.borrow_cost == pytest.approx(invested * 0.12 / 12)
    assert result.asset_notional_end.eq(0).all()
    balance = (result.capital_start - result.transaction_cost + result.price_pnl + result.dividend_pnl
               + result.cash_interest - result.borrow_cost - result.liquidation_cost)
    assert result.capital_end.tolist() == pytest.approx(balance.tolist())


def test_flip_and_short_rebalance_use_actual_traded_notional():
    parameters = {**PARAMETERS, "annual_borrow_rate": 0.0}
    components, signals = inputs([0.0, 0.0], reversal=[1, -1])
    rows = simulate_baselines(components, signals, parameters).query("strategy == 'reversal'").reset_index(drop=True)
    start = 100 / 1.01
    assert rows.loc[1, "trade_notional"] == pytest.approx(2 * start / 1.01)
    assert rows.loc[1, "capital_after_trading"] == pytest.approx(start * 0.99 / 1.01)
    components, signals = inputs([-0.2, 0.0], reversal=[-1, -1])
    rows = simulate_baselines(components, signals, parameters).query("strategy == 'reversal'").reset_index(drop=True)
    assert rows.loc[1, "trade_notional"] == pytest.approx(0.4 * start / 1.01)
    assert rows.loc[1, "transaction_cost"] > 0  # Señal idéntica, pero hay que reajustar el nominal.


def test_month_alignment_future_independence_and_insolvency():
    components, signals = inputs([0.01, -0.02, 0.03], dividends=[0.001] * 3, rf=[0.002] * 3)
    original = simulate_baselines(components, signals, PARAMETERS)
    changed = components.copy(); changed.loc[2, "price_return"] = -0.1
    after = simulate_baselines(changed, signals, PARAMETERS)
    pd.testing.assert_frame_equal(original.loc[original.period.lt("1927-03")].reset_index(drop=True),
                                  after.loc[after.period.lt("1927-03")].reset_index(drop=True))
    bad = signals.copy(); bad.loc[0, "decision_period"] = "1927-01"
    with pytest.raises(ValueError, match="mes anterior"):
        simulate_baselines(components, bad, PARAMETERS)
    bad = signals.copy(); bad.loc[0, "momentum_signal"] = pd.NA
    with pytest.raises(ValueError, match="ausente"):
        simulate_baselines(components, bad, PARAMETERS)
    components, signals = inputs([1.2])
    with pytest.raises(ValueError, match="insolvente"):
        simulate_baselines(components, signals, PARAMETERS)


def test_drawdown_includes_initial_capital_and_optional_dividends():
    components, signals = inputs([-0.1, 0.0], dividends=[0.02, 0.0], rf=[0.0, 0.0])
    parameters = {**PARAMETERS, "transaction_cost_rate": 0.0, "annual_borrow_rate": 0.0, "include_dividends": False}
    result = simulate_baselines(components, signals, parameters)
    summary = summarize_baselines(result, parameters)
    assert summary[0]["capital_final"] == pytest.approx(90.0)
    assert summary[0]["max_drawdown"] == pytest.approx(-0.1)  # También cuenta la pérdida del primer mes.
    assert result.dividend_pnl.eq(0).all()
    assert summary[0]["annualized_return"] == pytest.approx(0.9**6 - 1)


def test_cli_publication_settings_and_all_dependency_invalidations(tmp_path, monkeypatch, capsys):
    configs = tmp_path / "configs"; configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    workbook(monkeypatch)
    shiller = tmp_path / "shiller.xls"; shiller.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "french.zip"
    french.write_bytes(french_zip([f"{m.replace('-', '')},unused,unused,unused,0.2"
                                   for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepare_shiller_data(config, file=shiller); prepare_french_data(config, file=french)
    calculate_signals(config); prepare_return_components(config)
    assert cli.main(["simulate-baselines", "--config", str(config)]) == 0
    assert "Son resultados de desarrollo" in capsys.readouterr().out
    table, report = read_result(load_config(config), "baseline_simulations")
    assert len(table) == 2268 and report["last_period"] == "1989-12"
    assert report["liquidated_at_end"] and len(report["strategies"]) == 3
    assert table.groupby("strategy").tail(1).asset_notional_end.eq(0).all()
    assert report["strategies"][1]["sharpe"] is None
    previous_config = config.read_bytes()
    config.write_text(config.read_text().replace("transaction_cost_rate = 0.001", "transaction_cost_rate = 0.002"))
    with pytest.raises(ValueError, match="configuración"):
        read_result(load_config(config), "baseline_simulations")
    config.write_bytes(previous_config)
    path = tmp_path / "data/processed/baseline_simulations.parquet"
    calculate_signals(config)
    assert not path.exists() and not path.with_suffix(".json").exists()
    simulate_basic_strategies(config); prepare_return_components(config)
    assert not path.exists()
    simulate_basic_strategies(config); prepare_french_data(config)
    assert not path.exists()
    prepare_return_components(config); simulate_basic_strategies(config); prepare_shiller_data(config)
    assert not path.exists()
