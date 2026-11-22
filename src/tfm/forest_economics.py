"""Cuenta de reversión con RF_M1 en el desarrollo 1950–1989."""

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.boosting import load_boosting_inputs
from tfm.economics import (ACCOUNT_LABELS, DECISION_POLICY, RESULT_NAMES as LINEAR_ECONOMIC_RESULTS,
                           RISK_PARAMETERS, build_economic_decisions)
from tfm.simulation import simulate_baselines, summarize_baselines
from tfm.walk_forward import FIRST_TEST_YEAR, LAST_TEST_YEAR


RULE = "reversal"
MODEL = "RF_M1"
ACCOUNT = "reversal_rf_m1"
REFERENCE_ACCOUNTS = ("cash", "reversal", "reversal_bear", "reversal_volatility", "reversal_m1")
REPORT_LABELS = {**{name: ACCOUNT_LABELS[name] for name in REFERENCE_ACCOUNTS}, ACCOUNT: "Reversión · RF_M1"}
RESULT_NAMES = ("forest_economic_decisions", "forest_economic_simulations", "forest_economic_metrics")
TEST_INTERVAL = (f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12")


def load_forest_economic_inputs(root: Path) -> tuple:
    from tfm.data import read_result

    _, forecasts, source = load_boosting_inputs(root)
    simulations, report = read_result(root, LINEAR_ECONOMIC_RESULTS[1])
    metrics, metrics_report = read_result(root, LINEAR_ECONOMIC_RESULTS[2])
    if (not report.get("attempt") or metrics_report.get("attempt") != report["attempt"]
            or report.get("experiment_status") != "completed" or report.get("test_interval") != list(TEST_INTERVAL)
            or report.get("source_attempts", {}).get("M0_M1") != source["baseline_attempt"]
            or report.get("source_attempts", {}).get("M2") != source["reference_attempt"]
            or report.get("parameters") != source["parameters"] or report.get("decision_policy") != DECISION_POLICY
            or report.get("volatility_parameters") != RISK_PARAMETERS):
        raise ValueError("Ejecuta las secciones 19–22 del notebook 14 con las referencias actuales antes de simular RF_M1.")

    signals, _ = read_result(root, "shiller_signals")
    components, _ = read_result(root, "monthly_return_components")
    signals = signals.loc[signals.target_period.between(*TEST_INTERVAL)].reset_index(drop=True)
    components = components.loc[components.period.between(*TEST_INTERVAL)].reset_index(drop=True)
    reference_metrics = metrics.loc[metrics.strategy.isin(REFERENCE_ACCOUNTS)]
    attempts = {"forest": source["forest_attempt"], "economic_references": report["attempt"]}
    return signals, components, forecasts.loc[forecasts.strategy.eq(RULE)], simulations, reference_metrics, source["parameters"], attempts


def evaluate_forest_economics(signals: pd.DataFrame, components: pd.DataFrame, forecasts: pd.DataFrame,
                              references: pd.DataFrame, reference_metrics: pd.DataFrame, parameters: dict) -> dict:
    decisions = build_economic_decisions(signals, forecasts, rules=(RULE,),
                                         model_probabilities={MODEL: "probability_rf_m1"})
    references = references.loc[references.strategy.isin(REFERENCE_ACCOUNTS)]
    for name in REFERENCE_ACCOUNTS:
        rows = references.loc[references.strategy.eq(name)]
        if (rows.period.tolist() != signals.target_period.tolist()
                or rows.decision_period.tolist() != signals.decision_period.tolist()
                or not np.array_equal(rows.rf_return, components.rf_return)
                or rows.capital_start.iloc[0] != parameters["initial_capital"]
                or not np.array_equal(rows.capital_start.iloc[1:], rows.capital_end.iloc[:-1])):
            raise ValueError(f"La cuenta {name} no coincide con el calendario, el efectivo o el capital inicial de referencia.")
    filtered = signals.assign(reversal_signal=decisions.filtered_signal.to_numpy())
    candidate = simulate_baselines(components, filtered, parameters, strategies=(RULE,)).assign(strategy=ACCOUNT)
    accounts = pd.concat([references, candidate], ignore_index=True)
    metrics = pd.DataFrame(summarize_baselines(accounts, parameters, strategies=REPORT_LABELS))
    stored = reference_metrics.set_index("strategy")
    try:
        common = metrics.loc[metrics.strategy.isin(REFERENCE_ACCOUNTS)].set_index("strategy")
        pd.testing.assert_frame_equal(common, stored.loc[common.index, common.columns], check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("Las métricas guardadas de referencia no coinciden con sus cuentas mensuales.") from exc

    executed = accounts.loc[accounts.position.ne(0)].groupby("strategy").size()
    metrics["accepted_signals"] = metrics.strategy.map(executed).fillna(0).astype(int)
    cash_capital = float(metrics.loc[metrics.strategy.eq("cash"), "capital_final"].iloc[0])
    metrics["capital_difference_vs_cash"] = metrics.capital_final - cash_capital
    return dict(zip(RESULT_NAMES, [decisions, accounts, metrics], strict=True))


def run_forest_economics(root: Path) -> tuple[dict, dict]:
    *inputs, attempts = load_forest_economic_inputs(root)
    record = {"attempt": datetime.now(timezone.utc).isoformat(), "purpose": "reversal_rf_m1_continuous_account",
        "model": MODEL, "rule": RULE, "source_attempts": attempts, "test_interval": list(TEST_INTERVAL),
        "decision_policy": dict(DECISION_POLICY), "parameters": inputs[-1], "volatility_parameters": RISK_PARAMETERS}
    path = root / "outputs/experiments/forest_economics_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as history:
        def log_event(status: str, **details) -> None:
            history.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")
            history.flush()

        log_event("started")
        try:
            tables = evaluate_forest_economics(*inputs)
            log_event("completed", metrics=json.loads(tables[RESULT_NAMES[2]].to_json(orient="records")))
        except (Exception, KeyboardInterrupt) as exc:
            log_event("failed", error=str(exc))
            raise
    return tables, {**record, "experiment_status": "completed", "trial_log": str(path.relative_to(root)),
                    "protocol": "docs/evaluacion_economica_bosque.md"}
