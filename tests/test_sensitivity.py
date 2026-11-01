"""Sensibilidad prefijada: mismo simulador, efectos contables y flujo local."""


import pandas as pd
import pytest

from tfm.sensitivity import run_sensitivities, sensitivity_scenarios
from tfm.simulation import simulate_baselines, summarize_baselines
from test_simulation import inputs


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
