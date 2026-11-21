import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.annual_diagnostics import MODELS, build_annual_diagnostics


def inputs():
    months = pd.period_range("1950-01", "1989-12", freq="M")
    features = pd.DataFrame({"target_period": months.astype(str),
        "decision_period": (months-1).astype(str),
        "market_return_24m": np.where(months.month <= 6, -.1, .1),
        "price_volatility_12m": .1 + np.arange(len(months))/10000,
        "drawdown_12m": -.05})
    rows = []
    for rule in ("momentum", "reversal"):
        for month, label in (("1950-01", 1), ("1950-07", 0), ("1951-01", 1)):
            year = int(month[:4])
            rows.append({"strategy": rule, "target_period": month, "label": label,
                "test_year": year, "split_id": year-1949, **{c: .6 for c in MODELS.values()}})
    return pd.DataFrame(rows), features


def test_annual_diagnostics_keeps_empty_single_class_and_missing_predictions():
    predictions, features = inputs()
    result = build_annual_diagnostics(predictions, features)
    annual = result["annual"]
    assert len(annual) == 40*2*7 and len(result["operations"]) == 80 and len(result["market"]) == 40
    assert annual.loc[annual.test_year.eq(1950), "auc"].eq(.5).all()
    assert annual.loc[annual.test_year.eq(1951), "auc"].isna().all()
    assert annual.loc[annual.test_year.eq(1951), "auc_status"].eq("single_class").all()
    assert annual.loc[annual.test_year.eq(1951), "log_loss"].notna().all()
    empty = result["operations"].loc[lambda t: t.test_year.eq(1952)]
    assert empty.examples.eq(0).all() and empty.active_bear_months.eq(0).all()
    assert empty.active_mean_volatility_12m.isna().all()
    assert annual.loc[annual.test_year.eq(1952), "auc_status"].eq("no_examples").all()
    assert result["market"].calendar_months.eq(12).all() and result["market"].bear_months.eq(6).all()
    active = result["operations"].loc[lambda t: t.test_year.eq(1950)]
    assert active.active_bear_months.eq(1).all()
    np.testing.assert_allclose(active.active_mean_volatility_12m, (.1+.1006)/2)
    assert result["market"].iloc[0].mean_volatility_12m != active.iloc[0].active_mean_volatility_12m
    predictions.loc[0, "probability_rf_m2"] = np.nan
    unavailable = build_annual_diagnostics(predictions, features)["annual"].loc[
        lambda t: t.test_year.eq(1950) & t.strategy.eq("momentum") & t.model.eq("RF_M2")].iloc[0]
    assert unavailable.examples == 2 and pd.isna(unavailable.auc) and pd.isna(unavailable.log_loss)
    assert unavailable.auc_status == "unavailable_predictions"


def test_annual_context_requires_complete_calendar_and_previous_month():
    predictions, features = inputs()
    for bad in (features.iloc[1:], pd.concat([features, features.iloc[:1]])):
        with pytest.raises(ValueError):
            build_annual_diagnostics(predictions, bad)
    bad = features.copy()
    bad.loc[0, "decision_period"] = "1950-01"
    with pytest.raises(ValueError, match="anteriores"):
        build_annual_diagnostics(predictions, bad)
    bad = features.copy()
    bad.loc[0, "target_period"] = "1990-01"
    with pytest.raises(ValueError, match="1990"):
        build_annual_diagnostics(predictions, bad)
