"""Escalado causal, cuentas parciales y comparación conjunta sin red."""

from statistics import stdev
import math

import pandas as pd
import pytest

from tfm.simulation import simulate_baselines
from tfm.volatility import build_volatility_scale, validate_volatility_parameters
from tfm.sources.shiller import INSTRUMENT
from test_simulation import inputs, PARAMETERS


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
