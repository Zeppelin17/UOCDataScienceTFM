"""Filtro prefijado: historia, decisión anterior y contabilidad compartida."""

from pathlib import Path

import pandas as pd
import pytest

from tfm import cli, menu
from tfm.comparators import build_bear_signals, simulate_bear_comparison
from tfm.config import load_config
from tfm.data import (prepare_shiller_data, prepare_french_data, calculate_signals,
                      prepare_return_components, read_result, simulate_basic_strategies)
from tfm.simulation import simulate_baselines
from tfm.sources.shiller import INSTRUMENT, XLS_SIGNATURE
from test_shiller import workbook
from test_return_components import french_zip
from test_simulation import inputs, PARAMETERS
from test_menu import answer_with


def history():
    return pd.DataFrame({"asset": INSTRUMENT,
                         "period": pd.period_range("1924-12", "1927-03", freq="M").astype(str),
                         "price_monthly_mean": [*([100.0] * 24), 90.0, 100.0, 110.0, 80.0],
                         "dividend_annualized": [object() for _ in range(28)]})


def test_exact_24_month_window_zero_boundary_no_future_data_and_missing_history():
    monthly = history()
    _, signals = inputs([0.01] * 3, momentum=[1, 1, 0], reversal=[-1, 1, -1])
    original = signals.copy(deep=True)
    result = build_bear_signals(monthly, signals)
    assert result.lookback_start_period.tolist() == ["1924-12", "1925-01", "1925-02"]
    assert result.market_return_24m.tolist() == pytest.approx([-0.1, 0.0, 0.1])
    assert result.bear_market.tolist() == [True, False, False]
    assert result.momentum_signal.tolist() == [0, 1, 0]
    assert result.reversal_signal.tolist() == [0, 1, -1]
    assert result.original_momentum_signal.tolist() == [1, 1, 0]
    pd.testing.assert_frame_equal(signals, original)
    changed = monthly.copy(); changed.loc[25:, "price_monthly_mean"] = 1.0
    pd.testing.assert_frame_equal(build_bear_signals(changed, signals).iloc[:1], result.iloc[:1])
    # También funciona sin conservar precios posteriores a la última decisión.
    pd.testing.assert_frame_equal(build_bear_signals(monthly.iloc[:-1], signals), result)
    with pytest.raises(ValueError, match="Falta historia.*1924-12.*no se han recortado"):
        build_bear_signals(monthly.iloc[1:], signals)
    bad = signals.copy(); bad.loc[0, "momentum_signal"] = pd.NA
    with pytest.raises(ValueError, match="ausente"):
        build_bear_signals(monthly, bad)


def test_shared_engine_preserves_baselines_and_accounts_for_cash_and_costs():
    components, signals = inputs([0.01, -0.02, 0.015], dividends=[0.002] * 3,
                                 rf=[0.001] * 3, momentum=[1, 1, 0], reversal=[-1, 1, -1])
    baseline = simulate_baselines(components, signals, PARAMETERS)
    table = simulate_bear_comparison(components, signals, history(), PARAMETERS)
    assert len(table) == 15
    original = table.loc[table.strategy.isin(baseline.strategy), baseline.columns].reset_index(drop=True)
    pd.testing.assert_frame_equal(original, baseline)
    first = table.loc[table.period.eq("1927-01") & table.strategy.str.endswith("_bear")]
    assert first.position.eq(0).all() and first.transaction_cost.eq(0).all()
    assert first.borrow_cost.eq(0).all() and first.capital_end.eq(100.1).all()
    assert table.groupby("strategy").tail(1).asset_notional_end.eq(0).all()
    balance = (table.capital_start - table.transaction_cost + table.price_pnl + table.dividend_pnl
               + table.cash_interest - table.borrow_cost - table.liquidation_cost)
    assert table.capital_end.tolist() == pytest.approx(balance.tolist())
    no_bear = history(); no_bear["price_monthly_mean"] = 100.0
    unchanged = simulate_bear_comparison(components, signals, no_bear, PARAMETERS)
    for rule in ("momentum", "reversal"):
        raw = unchanged.loc[unchanged.strategy.eq(rule), baseline.columns].reset_index(drop=True)
        filtered = unchanged.loc[unchanged.strategy.eq(f"{rule}_bear"), baseline.columns].reset_index(drop=True)
        filtered["strategy"] = rule
        pd.testing.assert_frame_equal(raw, filtered)


def test_cli_menu_full_development_and_dependency_invalidations(tmp_path, monkeypatch, capsys):
    configs = tmp_path / "configs"; configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    assert cli.main(["simulate-bear-filter", "--config", str(config)]) == 1
    assert "Faltan" in capsys.readouterr().err
    workbook(monkeypatch)
    shiller = tmp_path / "shiller.xls"; shiller.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "french.zip"
    french.write_bytes(french_zip([f"{m.replace('-', '')},unused,unused,unused,0.2"
                                   for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepared = prepare_shiller_data(config, file=shiller)
    assert prepared["rows"] == 781 and prepared["history_rows"] == 25
    prepare_french_data(config, file=french); calculate_signals(config); prepare_return_components(config)
    simulate_basic_strategies(config)
    processed = tmp_path / "data/processed"
    before = {p: p.read_bytes() for p in processed.iterdir()}
    assert cli.main(["simulate-bear-filter", "--config", str(config)]) == 0
    assert all(p.read_bytes() == content for p, content in before.items())
    table, report = read_result(load_config(config), "bear_filter_simulations")
    assert len(table) == 3780 and report["months_per_strategy"] == 756
    assert report["first_period"] == "1927-01" and report["last_period"] == "1989-12"
    assert report["bear_months"] == report["blocked_momentum_signals"] == report["blocked_reversal_signals"] == 0
    assert len(report["strategies"]) == 5
    assert "no réplica" in capsys.readouterr().out
    monkeypatch.setattr(menu, "_clear_screen", lambda: None)
    answer_with(monkeypatch, ["10", "", "3", "8", "", "0", "0"])
    assert menu.interactive_menu(config) == 0
    assert "Primeras cinco filas" in capsys.readouterr().out
    saved_config = config.read_bytes()
    config.write_text(config.read_text().replace("annual_borrow_rate = 0.01", "annual_borrow_rate = 0.02"))
    with pytest.raises(ValueError, match="configuración"):
        read_result(load_config(config), "bear_filter_simulations")
    config.write_bytes(saved_config)
    path = processed / "bear_filter_simulations.parquet"
    saved = path.read_bytes(), path.with_suffix(".json").read_bytes()
    for regenerate in (calculate_signals, prepare_return_components, prepare_french_data, prepare_shiller_data):
        path.write_bytes(saved[0]); path.with_suffix(".json").write_bytes(saved[1])
        regenerate(config)
        assert not path.exists() and not path.with_suffix(".json").exists()
