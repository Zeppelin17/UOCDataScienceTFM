"""Comparación emparejada de la cuenta RF_M1 y sus referencias guardadas."""

import pandas as pd
import pytest

from tfm.data import read_result, save_result
from tfm.economics import RESULT_NAMES as ECONOMIC_RESULTS, evaluate_economics
from tfm.forest import RESULT_NAMES as FOREST_RESULTS
from tfm.forest_economics import ACCOUNT, REFERENCE_ACCOUNTS, RESULT_NAMES, evaluate_forest_economics
from test_economics import economic_inputs


def test_forest_account_keeps_calendar_direction_and_costs():
    monthly, signals, components, forecasts, parameters, _ = economic_inputs()
    previous, _ = evaluate_economics(monthly, signals, components, forecasts, parameters)
    forest = forecasts.loc[forecasts.strategy.eq("reversal")].assign(probability_rf_m1=.5)
    forest.loc[forest.index[0], "probability_rf_m1"] = .5000001
    references = previous[ECONOMIC_RESULTS[1]]
    metrics = previous[ECONOMIC_RESULTS[2]]
    result = evaluate_forest_economics(signals, components, forest, references, metrics, parameters)
    decisions, accounts, summary = result.values()
    assert decisions.accepted.sum() == 1 and decisions.target_period.iloc[-1] == "1989-12"
    candidate = accounts.loc[accounts.strategy.eq(ACCOUNT)].reset_index(drop=True)
    assert candidate.position.iloc[:2].tolist() == [-1, 0]
    assert candidate.borrow_cost.iloc[0] > 0 and candidate.transaction_cost.iloc[1] > 0
    assert candidate.asset_notional_end.iloc[-1] == 0
    assert summary.loc[summary.strategy.eq(ACCOUNT), "accepted_signals"].item() == 1
    assert summary.loc[summary.strategy.eq("cash"), "accepted_signals"].item() == 0
    pd.testing.assert_frame_equal(accounts.loc[accounts.strategy.ne(ACCOUNT)].reset_index(drop=True),
        references.loc[references.strategy.isin(REFERENCE_ACCOUNTS)].reset_index(drop=True), check_exact=True)

    with pytest.raises(ValueError, match="predicción"):
        evaluate_forest_economics(signals, components, forest.iloc[1:], references, metrics, parameters)
    outside = pd.concat([forest, forest.iloc[:1].assign(target_period="1990-01", test_year=1990, split_id=41)])
    with pytest.raises(ValueError, match="predicción"):
        evaluate_forest_economics(signals, components, outside, references, metrics, parameters)


def test_replacing_either_reference_invalidates_the_forest_account(tmp_path):
    table = pd.DataFrame({"fixture": [1]})
    for upstream in (FOREST_RESULTS[0], ECONOMIC_RESULTS[1]):
        for name in RESULT_NAMES:
            save_result(tmp_path, name, table, {})
        save_result(tmp_path, upstream, table, {})
        pd.testing.assert_frame_equal(read_result(tmp_path, upstream)[0], table)
        for name in RESULT_NAMES:
            with pytest.raises(ValueError, match="secciones 40–41"):
                read_result(tmp_path, name)
