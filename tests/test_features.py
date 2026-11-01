"""Fórmulas manuales, retrasos y ausencia de dependencia de meses posteriores."""

import math
from statistics import stdev

import pandas as pd
import pytest

from tfm.diagnostics import INDUSTRIES
from tfm.features import FEATURE_COLUMNS, build_monthly_features
from tfm.sources.shiller import INSTRUMENT


def inputs():
    months = pd.period_range("1924-12", "1989-12", freq="M").astype(str)
    prices = pd.DataFrame({"asset": INSTRUMENT, "period": months, "price_monthly_mean": 100.0})
    months = pd.period_range("1926-07", "1989-12", freq="M").astype(str)
    industries = pd.DataFrame({"period": months,
                               **{name: 0.01 if i < 6 else -0.01 for i, name in enumerate(INDUSTRIES)}})
    months = pd.period_range("1919-01", "1989-12", freq="M").astype(str)
    baa = pd.DataFrame({"period": months, "yield_percent": 7.0})
    aaa = pd.DataFrame({"period": months, "yield_percent": 6.0})
    return prices, industries, baa, aaa


def test_manual_features_lag_units_and_initial_breadth_not_zero():
    prices, industries, baa, aaa = inputs()
    prices.loc[prices.period.eq("1975-03"), "price_monthly_mean"] = 80.0
    prices.loc[prices.period.eq("1975-04"), "price_monthly_mean"] = 90.0
    baa.loc[baa.period.eq("1975-03"), "yield_percent"] = 8.0
    baa.loc[baa.period.eq("1975-04"), "yield_percent"] = 20.0  # Aún no se usa para el objetivo mayo.
    table = build_monthly_features(prices, industries, baa, aaa)
    row = table.set_index("target_period").loc["1975-05"]
    assert row.price_source_period == row.decision_period == "1975-04"
    assert row.context_source_period == "1975-03"
    assert row.price_return_1m == pytest.approx(90 / 80 - 1)
    assert row.momentum_12_1 == pytest.approx(80 / 100 - 1)
    assert row.distance_ma_3m == pytest.approx(90 / ((100 + 80 + 90) / 3) - 1)
    assert row.distance_ma_12m == pytest.approx(90 / (1170 / 12) - 1)
    assert row.drawdown_12m == pytest.approx(-0.1)
    assert row.price_volatility_12m == pytest.approx(stdev([0.0] * 10 + [-0.2, 0.125]) * math.sqrt(12))
    assert row.credit_spread_pp == 2 and row.credit_spread_change_pp == 1
    assert row.industry_breadth_12m == 0.5
    assert row.industry_dispersion == pytest.approx(math.sqrt(12 / 11) * 0.01)
    assert len(table) == 756 and table.features_ready.sum() == 749
    assert table.loc[:6, "industry_breadth_12m"].isna().all()
    assert table.loc[7, "target_period"] == "1927-08" and table.loc[7, "features_ready"]
    assert not table[FEATURE_COLUMNS[:-2]].isna().any().any()
    # Igualdad con la media no significa superarla.
    flat = industries.copy(); flat[INDUSTRIES] = 0.0
    assert build_monthly_features(prices, flat, baa, aaa).loc[7:, "industry_breadth_12m"].eq(0).all()


def test_price_and_context_cutoffs_ignore_later_values_and_dividends():
    prices, industries, baa, aaa = inputs()
    expected = build_monthly_features(prices, industries, baa, aaa)
    prices.loc[prices.period.ge("1975-05"), "price_monthly_mean"] = 120.0
    prices["dividend_annualized"] = float("nan")  # No es una característica ni se consulta.
    industries.loc[industries.period.ge("1975-04"), INDUSTRIES] = 0.02
    baa.loc[baa.period.ge("1975-04"), "yield_percent"] = 12.0
    aaa.loc[aaa.period.ge("1975-04"), "yield_percent"] = 8.0
    actual = build_monthly_features(prices, industries, baa, aaa)
    pd.testing.assert_frame_equal(expected.loc[expected.target_period.le("1975-05")],
                                  actual.loc[actual.target_period.le("1975-05")])
    assert actual.loc[actual.target_period.eq("1975-06"), "price_return_1m"].iloc[0] == pytest.approx(0.2)
    assert actual.loc[actual.target_period.eq("1975-06"), "credit_spread_pp"].iloc[0] == 4.0


def test_missing_duplicate_nonfinite_or_future_inputs_are_not_repaired():
    prices, industries, baa, aaa = inputs()
    bad = industries.drop(index=20)
    with pytest.raises(ValueError, match="Meses ausentes"):
        build_monthly_features(prices, bad, baa, aaa)
    with pytest.raises(ValueError, match="duplicados"):
        build_monthly_features(prices, pd.concat([industries.iloc[:1], industries]), baa, aaa)
    bad = industries.copy(); bad.loc[20, INDUSTRIES[0]] = -1.0
    with pytest.raises(ValueError, match="-100"):
        build_monthly_features(prices, bad, baa, aaa)
    bad = baa.copy(); bad.loc[20, "yield_percent"] = float("nan")
    with pytest.raises(ValueError, match="Valores inválidos"):
        build_monthly_features(prices, industries, bad, aaa)
    future = pd.concat([prices, pd.DataFrame({"asset": [INSTRUMENT], "period": ["1990-01"], "price_monthly_mean": [1.0]})])
    with pytest.raises(ValueError, match="desde 1990"):
        build_monthly_features(future, industries, baa, aaa)
