"""Ventanas, direcciones y ausencia de dependencia de resultados futuros."""

import pandas as pd
import pytest

from tfm.signals.shiller import build_price_signals
from tfm.sources.shiller import INSTRUMENT


def test_fixed_windows_directions_and_no_future_dependency():
    table = pd.DataFrame({
        "asset": INSTRUMENT,
        "period": pd.period_range("1926-01", periods=14, freq="M").astype(str),
        "price_monthly_mean": [100, *([110] * 10), 50, 130, 130],
        "dividend_annualized": [object() for _ in range(14)],  # No debe consultarse.
    })
    result = build_price_signals(table)
    assert pd.isna(result.loc[11, "momentum_signal"])
    assert result.loc[12, "momentum_score"] == pytest.approx(-0.5)
    assert result.loc[12, "momentum_signal"] == 0
    assert result.loc[12, "reversal_signal"] == -1
    assert result.loc[11, "reversal_signal"] == 1
    assert result.loc[13, "momentum_signal"] == 1
    assert result.loc[13, "reversal_signal"] == 0
    assert result.loc[12, "decision_period"] == "1927-01"
    assert result.loc[12, "target_period"] == "1927-02"
    pd.testing.assert_frame_equal(build_price_signals(table.iloc[:13]), result.iloc[:13])
    changed = table.copy()
    changed.loc[13, "price_monthly_mean"] = 1
    pd.testing.assert_frame_equal(build_price_signals(changed).iloc[:13], result.iloc[:13])
    changed.loc[12, "price_monthly_mean"] = 300
    assert build_price_signals(changed).loc[12, "momentum_score"] == result.loc[12, "momentum_score"]
