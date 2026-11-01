"""Filtro prefijado: historia, decisión anterior y contabilidad compartida."""


import pandas as pd
import pytest

from tfm.comparators import build_bear_signals, simulate_bear_comparison
from tfm.simulation import simulate_baselines
from tfm.sources.shiller import INSTRUMENT
from test_simulation import inputs, PARAMETERS


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
