"""Puerta fija, cuentas continuas y publicación sin volver a ajustar modelos."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tfm.data import read_result, save_result
from tfm.economics import (MODEL_PROBABILITIES, RESULT_NAMES, build_economic_decisions,
                           evaluate_economics, load_economic_inputs, run_economics)
from tfm.sources.shiller import INSTRUMENT
from tfm.walk_forward import M3_COLUMNS, INTERACTION_RESULTS, INTERACTION_VARIANT, REGIME_VARIANT
from tfm.logistic import MODEL_PARAMETERS


PARAMETERS = {"initial_capital": 100., "transaction_cost_rate": .001,
              "annual_borrow_rate": .01, "include_dividends": True}


def economic_inputs():
    history = pd.period_range("1947-01", "1989-12", freq="M")
    prices = 100*np.cumprod(1+.003+.012*np.sin(np.arange(len(history))))
    monthly = pd.DataFrame({"asset": INSTRUMENT, "period": history.astype(str), "price_monthly_mean": prices})
    months = pd.period_range("1950-01", "1989-12", freq="M")
    i = np.arange(len(months))
    components = pd.DataFrame({"asset": INSTRUMENT, "period": months.astype(str),
        "previous_period": (months-1).astype(str), "price_return": .003+.012*np.sin(i+36),
        "dividend_return_approx": .002, "rf_return": .001+.0001*np.cos(i)})
    signals = pd.DataFrame({"asset": INSTRUMENT, "basis": "monthly_mean_price",
        "target_period": months.astype(str), "decision_period": (months-1).astype(str),
        "momentum_signal": np.where(i % 5, 1, 0), "reversal_signal": np.resize([-1, 1, 0, 1], len(i))})
    parts = []
    for rule in ("momentum", "reversal"):
        active = signals[f"{rule}_signal"].ne(0)
        dates = months[active]
        parts.append(pd.DataFrame({"strategy": rule, "target_period": dates.astype(str),
            "test_year": dates.year, "split_id": dates.year-1949, "label": np.arange(len(dates)) % 2,
            "probability_naive": .6, "probability_logistic": .7,
            "probability_regime": 0., "probability_interaction": 1.}))
    predictions = pd.concat(parts, ignore_index=True)
    predictions.loc[:2, "probability_logistic"] = [.5, .5000001, .2]
    return monthly, signals, components, predictions, PARAMETERS.copy(), {"M0_M1": "a", "M2": "b", "M3": "c"}


def test_fixed_gate_cash_and_continuous_account_with_costs():
    monthly, signals, components, predictions, parameters, _ = economic_inputs()
    decisions = build_economic_decisions(signals, predictions)
    m1 = decisions.loc[decisions.rule.eq("momentum") & decisions.model.eq("M1")]
    active = m1.loc[m1.original_signal.ne(0)].reset_index(drop=True)
    assert active.accepted.iloc[:3].tolist() == [False, True, False]
    assert m1.loc[m1.original_signal.eq(0), "probability"].isna().all()
    assert m1.loc[m1.original_signal.eq(0), "decision_status"].eq("no_original_signal").all()
    changed = predictions.copy(); changed["label"] = 1-changed.label
    pd.testing.assert_frame_equal(decisions, build_economic_decisions(signals, changed), check_exact=True)
    with pytest.raises(ValueError, match="predicción"):
        build_economic_decisions(signals, predictions.iloc[1:])
    for value in (np.nan, np.inf, -.1, 1.1):
        bad = predictions.copy(); bad.loc[0, "probability_regime"] = value
        with pytest.raises(ValueError, match="probabilidades"):
            build_economic_decisions(signals, bad)
    tables, _ = evaluate_economics(monthly, signals, components, predictions, parameters)
    accounts = tables[RESULT_NAMES[1]]; metrics = tables[RESULT_NAMES[2]].set_index("strategy")
    assert len(accounts) == 16*480 and len(metrics) == 16 and metrics.months.eq(480).all()
    for rule in ("momentum", "reversal"):
        raw = accounts.loc[accounts.strategy.eq(rule)].drop(columns="strategy").reset_index(drop=True)
        accepted = accounts.loc[accounts.strategy.eq(rule+"_m3")].drop(columns="strategy").reset_index(drop=True)
        pd.testing.assert_frame_equal(raw, accepted, check_exact=True)
        cash = accounts.loc[accounts.strategy.eq("cash")].drop(columns="strategy").reset_index(drop=True)
        rejected = accounts.loc[accounts.strategy.eq(rule+"_m2")].drop(columns="strategy").reset_index(drop=True)
        pd.testing.assert_frame_equal(cash, rejected, check_exact=True)
        assert pd.isna(metrics.loc[rule+"_m2", "sharpe"])
        assert metrics.loc[rule+"_m2", "accepted_signals"] == 0
    assert accounts.groupby("strategy").head(1).capital_start.eq(100).all()
    assert accounts.groupby("strategy").tail(1).asset_notional_end.eq(0).all()
    for _, rows in accounts.groupby("strategy", sort=False):
        np.testing.assert_array_equal(rows.capital_start.iloc[1:], rows.capital_end.iloc[:-1])
        assert rows.iloc[:-1].liquidation_cost.eq(0).all()
    # Rechazar una señal después de abrir una posición paga su cierre real.
    rows = accounts.loc[accounts.strategy.eq("momentum_m1")].reset_index(drop=True)
    assert rows.loc[2, "position"] == 1 and rows.loc[3, "position"] == 0
    assert rows.loc[3, "transaction_cost"] > 0
    balance = (accounts.capital_start-accounts.transaction_cost+accounts.price_pnl+accounts.dividend_pnl
               +accounts.cash_interest-accounts.borrow_cost-accounts.liquidation_cost)
    np.testing.assert_allclose(accounts.capital_end, balance, rtol=0, atol=1e-10)
    comparisons = tables[RESULT_NAMES[3]]
    assert len(comparisons) == 30
    assert comparisons.loc[comparisons.model.eq("M2"), "comparison_status"].eq("unavailable_sharpe").all()


def test_economic_notebook_independent_section_history_and_invalidation(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    monkeypatch.setattr("tfm.economics.load_economic_inputs", lambda root: economic_inputs())
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    notebook = json.loads((Path(__file__).parents[1]/"notebooks/14_referencia_walk_forward.ipynb").read_text())
    namespace = {}
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code" and "economics" in c.get("metadata", {}).get("tags", [])]
    assert len(cells) == 4
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:economics", "exec"), namespace)
    plt.close("all")
    for name in RESULT_NAMES:
        saved, info = read_result(tmp_path, name)
        pd.testing.assert_frame_equal(saved, namespace["tablas_economicas"][name], check_exact=True)
        assert info["source_attempts"] == {"M0_M1": "a", "M2": "b", "M3": "c"}
    log = tmp_path/namespace["informe_economico"]["trial_log"]
    assert [json.loads(l)["status"] for l in log.read_text().splitlines()] == ["started", "completed"]
    paths = {tmp_path/"data/processed"/f"{name}.{ext}": (tmp_path/"data/processed"/f"{name}.{ext}").read_bytes()
             for name in RESULT_NAMES for ext in ("parquet", "json")}
    def failed(*a, **k):raise RuntimeError("Fallo económico simulado")
    monkeypatch.setattr("tfm.economics.evaluate_economics", failed)
    with pytest.raises(RuntimeError, match="Fallo económico"):
        run_economics(tmp_path)
    assert all(p.read_bytes() == data for p, data in paths.items())
    assert [json.loads(l)["status"] for l in log.read_text().splitlines()][-2:] == ["started", "failed"]
    for name in ("cpcv_regime_metrics", "logistic_metrics", "walk_forward_ablation_metrics", "screening_tests"):
        save_result(tmp_path, name, pd.DataFrame({"fixture": [1]}), {})
        assert all(p.read_bytes() == data for p, data in paths.items())
    for name in ("walk_forward_predictions", "walk_forward_regime_metrics", "walk_forward_interaction_metrics",
                 "monthly_features", "labelled_signals"):
        for p, data in paths.items():p.write_bytes(data)
        save_result(tmp_path, name, pd.DataFrame({"fixture": [1]}), {})
        assert all(not p.exists() for p in paths) and log.exists()


def test_m3_lineage_and_inherited_probabilities_checked_before_economics(tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    from tfm.walk_forward import summarize_walk_forward_predictions
    monthly, signals, components, predictions, parameters, origins = economic_inputs()
    inherited = predictions.drop(columns="probability_interaction")
    report = {"variant": INTERACTION_VARIANT, "model_columns": M3_COLUMNS,
        "reference_variant": REGIME_VARIANT, "target": "label", "model_parameters": MODEL_PARAMETERS,
        "test_interval": ["1950-01", "1989-12"], "window": "expanding", "refit": "annual", "purge_months": 1,
        "interaction": {"raw_formula": "1(market_return_24m < 0) * price_volatility_12m"},
        "versions": {}, "parameters": parameters, "reference_attempt": "b", "baseline_attempt": "a",
        "experiment_status": "completed", "attempt": "c"}
    sources = {INTERACTION_RESULTS[0]: predictions,
               INTERACTION_RESULTS[1]: summarize_walk_forward_predictions(predictions, models={"M3": "probability_interaction"}),
               INTERACTION_RESULTS[2]: pd.DataFrame(), INTERACTION_RESULTS[3]: pd.DataFrame(),
               "shiller_signals": signals, "monthly_return_components": components}
    monkeypatch.setattr("tfm.economics.load_walk_forward_inputs", lambda root: (None, {"parameters": parameters}, None))
    monkeypatch.setattr("tfm.economics.load_walk_forward_regime_reference", lambda *args:
        ({"walk_forward_regime_predictions": inherited}, {"versions": {}, "attempt": "b", "reference_attempt": "a"}))
    monkeypatch.setattr("tfm.data.read_result", lambda root, name: (sources[name], report))
    monkeypatch.setattr("tfm.data.load_monthly", lambda root: monthly)
    assert load_economic_inputs(tmp_path)[-1] == origins
    report["baseline_attempt"] = "another-reference"
    with pytest.raises(ValueError, match="referencias actuales"):
        load_economic_inputs(tmp_path)
    report["baseline_attempt"] = "a"
    sources[INTERACTION_RESULTS[0]] = predictions.copy()
    sources[INTERACTION_RESULTS[0]].loc[0, "probability_logistic"] = .9
    with pytest.raises(ValueError, match="no coincide"):
        load_economic_inputs(tmp_path)
