"""Cuentas continuas con probabilidades walk-forward y umbral fijo, sin reentrenar."""

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.logistic import MODEL_PARAMETERS
from tfm.screening import RULES
from tfm.simulation import simulate_baselines, summarize_baselines
from tfm.volatility import simulate_simple_comparison
from tfm.validation import PURGE_MONTHS
from tfm.walk_forward import (FIRST_TEST_YEAR, LAST_TEST_YEAR, M3_COLUMNS, INTERACTION_VARIANT,
    REGIME_VARIANT, INTERACTION_RESULTS, load_walk_forward_inputs,
    load_walk_forward_regime_reference, summarize_walk_forward_predictions)


THRESHOLD = .5
DECISION_POLICY = {"threshold": THRESHOLD, "operator": ">", "tie": "cash",
    "no_signal": "cash_without_prediction", "missing_active_prediction": "stop",
    "sizing": "original_signal_or_cash", "threshold_selection": "fixed_without_search"}
MODEL_PROBABILITIES = {"M0": "probability_naive", "M1": "probability_logistic",
                       "M2": "probability_regime", "M3": "probability_interaction"}
RISK_PARAMETERS = {"lookback_months": 12, "target_annual_volatility": .12, "max_exposure": 1.0}
RESULT_NAMES = ("walk_forward_economic_decisions", "walk_forward_economic_simulations",
                "walk_forward_economic_metrics", "walk_forward_economic_comparison")
ACCOUNT_LABELS = {"buy_and_hold": "Comprar y mantener", "cash": "Efectivo",
    **{rule: name for rule, name in zip(RULES, ("Momentum", "Reversión"))},
    **{f"{rule}_{method}": f"{name} · {label}"
       for rule, name in zip(RULES, ("Momentum", "Reversión"))
       for method, label in {"bear": "veto bajista", "volatility": "ajuste por volatilidad",
                             **{m.lower(): m for m in MODEL_PROBABILITIES}}.items()}}


def build_economic_decisions(signals: pd.DataFrame, predictions: pd.DataFrame, *, rules: tuple[str, ...] = RULES,
                             model_probabilities: dict[str, str] | None = None) -> pd.DataFrame:
    """Una fila por mes, regla y filtro; ausencia de pronóstico activo es error."""
    models = MODEL_PROBABILITIES if model_probabilities is None else model_probabilities
    if not rules or len(set(rules)) != len(rules) or not set(rules) <= set(RULES) or not models:
        raise ValueError("Se necesitan modelos de probabilidad y reglas de inversión válidas.")
    months = pd.period_range(f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12", freq="M")
    required = {"target_period", "decision_period", "momentum_signal", "reversal_signal"}
    if (not required <= set(signals) or signals.target_period.tolist() != months.astype(str).tolist()
            or signals.decision_period.tolist() != (months-1).astype(str).tolist()):
        raise ValueError("Las decisiones requieren todos los meses de 1950–1989, ordenados y sin huecos.")
    fields = {"strategy", "target_period", "split_id", "test_year", *models.values()}
    if not fields <= set(predictions) or predictions.duplicated(["strategy", "target_period"]).any():
        raise ValueError("Se necesita una predicción cronológica única por señal activa.")
    expected = pd.concat([pd.DataFrame({"strategy": rule,
        "target_period": signals.loc[signals[f"{rule}_signal"].ne(0), "target_period"]}) for rule in rules], ignore_index=True)
    keys = ["strategy", "target_period"]
    try:
        pd.testing.assert_frame_equal(predictions[keys].sort_values(keys).reset_index(drop=True),
                                      expected.sort_values(keys).reset_index(drop=True), check_exact=True)
    except AssertionError as exc:
        raise ValueError("Falta o sobra una predicción para las señales activas; no se ha convertido en efectivo.") from exc
    years = pd.PeriodIndex(predictions.target_period, freq="M").year
    if (not np.array_equal(predictions.test_year, years)
            or not np.array_equal(predictions.split_id, years-FIRST_TEST_YEAR+1)):
        raise ValueError("Las probabilidades no corresponden a los años walk-forward previstos.")
    for column in models.values():
        values = predictions[column]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all()
                or not values.between(0, 1).all()):
            raise ValueError("Toda señal activa requiere probabilidades finitas entre cero y uno.")
    records = []
    for model, column in models.items():
        for rule in rules:
            rows = signals[["target_period", "decision_period", f"{rule}_signal"]].rename(
                columns={f"{rule}_signal": "original_signal"}).copy()
            rows = rows.merge(predictions.loc[predictions.strategy.eq(rule), ["target_period", column]],
                              on="target_period", how="left", validate="one_to_one").rename(columns={column: "probability"})
            rows["model"] = model; rows["rule"] = rule
            active = rows.original_signal.ne(0)
            rows["accepted"] = active & rows.probability.gt(THRESHOLD)
            rows["filtered_signal"] = rows.original_signal.where(rows.accepted, 0)
            rows["decision_status"] = np.select([~active, rows.accepted],
                                               ["no_original_signal", "accepted"], default="rejected")
            records.append(rows)
    return pd.concat(records, ignore_index=True)


def compare_economic_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    """Diferencias descriptivas; una cuenta con Sharpe ausente no supera un control."""
    scores = metrics.set_index("strategy")
    pairs = [(rule, model, reference, f"{rule}_{model.lower()}", f"{rule}{suffix}")
        for rule in RULES for model in MODEL_PROBABILITIES
        for reference, suffix in (("unfiltered", ""), ("bear", "_bear"), ("volatility", "_volatility"))]
    pairs += [(rule, candidate, reference, f"{rule}_{candidate.lower()}", f"{rule}_{reference.lower()}")
              for rule in RULES for candidate, reference in (("M2", "M1"), ("M3", "M1"), ("M3", "M2"))]
    records = []
    for rule, model, reference, candidate_account, reference_account in pairs:
        a, b = scores.loc[candidate_account], scores.loc[reference_account]
        available = bool(pd.notna(a.sharpe) and pd.notna(b.sharpe))
        records.append({"rule": rule, "model": model, "reference": reference,
            "candidate_account": candidate_account, "reference_account": reference_account,
            "sharpe_candidate": a.sharpe, "sharpe_reference": b.sharpe,
            "sharpe_improvement": float(a.sharpe-b.sharpe) if available else None,
            "comparison_status": "available" if available else "unavailable_sharpe"})
    return pd.DataFrame(records)


def evaluate_economics(monthly: pd.DataFrame, signals: pd.DataFrame, components: pd.DataFrame,
                       predictions: pd.DataFrame, parameters: dict) -> tuple[dict, dict]:
    decisions = build_economic_decisions(signals, predictions)
    original = simulate_simple_comparison(components, signals, monthly, parameters, RISK_PARAMETERS)
    # Conservar las columnas contables del motor, sin mezclar sus contextos auxiliares.
    empty_signals = signals.copy()
    empty_signals[["momentum_signal", "reversal_signal"]] = 0
    cash = simulate_baselines(components, empty_signals, parameters).loc[lambda t: t.strategy.eq("momentum")].copy()
    cash["strategy"] = "cash"
    accounts = [original.loc[original.strategy.isin(ACCOUNT_LABELS), cash.columns], cash]
    for model in MODEL_PROBABILITIES:
        filtered = signals.copy()
        for rule in RULES:
            values = decisions.loc[decisions.model.eq(model) & decisions.rule.eq(rule)]
            filtered[f"{rule}_signal"] = values.filtered_signal.to_numpy()
        simulated = simulate_baselines(components, filtered, parameters)
        simulated = simulated.loc[simulated.strategy.isin(RULES)].copy()
        simulated["strategy"] += "_"+model.lower()
        accounts.append(simulated)
    simulations = pd.concat(accounts, ignore_index=True)
    metrics = pd.DataFrame(summarize_baselines(simulations, parameters, strategies=ACCOUNT_LABELS))
    for model in MODEL_PROBABILITIES:
        for rule in RULES:
            rows = decisions.loc[decisions.model.eq(model) & decisions.rule.eq(rule)]
            mask = metrics.strategy.eq(f"{rule}_{model.lower()}")
            metrics.loc[mask, "active_signals"] = int(rows.original_signal.ne(0).sum())
            metrics.loc[mask, "accepted_signals"] = int(rows.accepted.sum())
            metrics.loc[mask, "rejected_signals"] = int(rows.decision_status.eq("rejected").sum())
    for column in ("active_signals", "accepted_signals", "rejected_signals"):
        metrics[column] = metrics[column].astype("Int64")
    comparisons = compare_economic_metrics(metrics)
    report = {"scope": "development_walk_forward_economic_diagnostic",
        "test_interval": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"],
        "decision_policy": dict(DECISION_POLICY),
        "parameters": parameters, "volatility_parameters": RISK_PARAMETERS, "months_per_account": 480,
        "accounts": ACCOUNT_LABELS, "model_probabilities": MODEL_PROBABILITIES,
        "experiment_status": "completed", "regime_acceptance": "not_assessed_economic_comparison_only",
        "warnings": ["Development results after prior predictive inspection; not independent confirmation.",
            "No CPCV probability averages or isolated label returns used to construct equity curves.",
            "Same initial cash, continuous account across years, final liquidation only.",
            "Fixed 0.5 classification threshold is not a calibrated or payoff-optimal decision rule.",
            "Monthly means and reconstructed dividends are retrospective approximations, not executable trades.",
            "Economic improvement does not override failed annual predictive stability.",
            "No model fitting, threshold search, DSR/PBO, SHAP or post-1989 data."]}
    return dict(zip(RESULT_NAMES, [decisions, simulations, metrics, comparisons])), report


def load_economic_inputs(root: Path) -> tuple:
    from tfm.data import read_result, load_monthly

    samples, label_report, _ = load_walk_forward_inputs(root)
    reference, original = load_walk_forward_regime_reference(root, samples, label_report)
    stored = {name: read_result(root, name) for name in INTERACTION_RESULTS}
    report = stored["walk_forward_interaction_metrics"][1]
    if (report.get("variant") != INTERACTION_VARIANT or report.get("model_columns") != M3_COLUMNS
            or report.get("reference_variant") != REGIME_VARIANT or report.get("target") != "label"
            or report.get("model_parameters") != MODEL_PARAMETERS or report.get("versions") != original["versions"]
            or report.get("test_interval") != [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"]
            or report.get("window") != "expanding" or report.get("refit") != "annual"
            or report.get("purge_months") != PURGE_MONTHS
            or report.get("interaction", {}).get("raw_formula") != "1(market_return_24m < 0) * price_volatility_12m"
            or report.get("parameters") != label_report["parameters"]
            or report.get("reference_attempt") != original["attempt"]
            or report.get("baseline_attempt") != original["reference_attempt"]
            or report.get("experiment_status") != "completed" or not report.get("attempt")
            or any(info.get("attempt") != report["attempt"] for _, info in stored.values())):
        raise ValueError("Ejecuta la parte M3 del notebook 14 con las referencias actuales antes de simular.")
    predictions = stored["walk_forward_interaction_predictions"][0]
    try:
        baseline = reference["walk_forward_regime_predictions"]
        pd.testing.assert_frame_equal(predictions[baseline.columns], baseline, check_exact=True)
        pd.testing.assert_frame_equal(summarize_walk_forward_predictions(predictions,
            models={"M3": "probability_interaction"}), stored["walk_forward_interaction_metrics"][0], check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("M3 no coincide con las referencias actuales; repite su sección del notebook 14.") from exc
    signals, _ = read_result(root, "shiller_signals")
    components, _ = read_result(root, "monthly_return_components")
    start, end = f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"
    signals = signals.loc[signals.target_period.between(start, end)].reset_index(drop=True)
    components = components.loc[components.period.between(start, end)].reset_index(drop=True)
    origins = {"M0_M1": original["reference_attempt"], "M2": original["attempt"], "M3": report["attempt"]}
    return load_monthly(root), signals, components, predictions, label_report["parameters"], origins


def run_economics(root: Path) -> tuple[dict, dict]:
    monthly, signals, components, predictions, parameters, origins = load_economic_inputs(root)
    attempt = datetime.now(timezone.utc).isoformat()
    path = root/"outputs/experiments/walk_forward_economics_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"attempt": attempt, "purpose": "fixed_threshold_continuous_economic_evaluation",
        "source_attempts": origins, "models": list(MODEL_PROBABILITIES), "strategies": list(RULES),
        "threshold": THRESHOLD, "operator": ">", "parameters": parameters,
        "volatility_parameters": RISK_PARAMETERS, "threshold_search": False,
        "test_interval": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"], "guide_version": "2026-11-15"}
    def append(event):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False)+"\n")
    append({"status": "started"})
    try:
        tables, report = evaluate_economics(monthly, signals, components, predictions, parameters)
        append({"status": "completed", "metrics": json.loads(tables[RESULT_NAMES[2]].to_json(orient="records"))})
    except (Exception, KeyboardInterrupt) as exc:
        append({"status": "failed", "error": str(exc)}); raise
    report.update(attempt=attempt, source_attempts=origins, trial_log=str(path.relative_to(root)),
                  guide_version="2026-11-15", protocol="docs/evaluacion_economica.md")
    return tables, report
