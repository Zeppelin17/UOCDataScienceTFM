"""Referencia M0/M1 de la guía del 28 de noviembre, con 120 meses de historia."""

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from tfm.cpcv_regime import evaluate_cpcv_candidate
from tfm.screening import REGIME_MIN_HISTORY, RULES
from tfm.validation import REGIME_CPCV_START, REGIME_RESULT_NAMES, summarize_validation
from tfm.walk_forward import (FIRST_TEST_YEAR, LAST_TEST_YEAR, MODEL_PARAMETERS, SIGNAL_COLUMNS,
                              VARIANT, evaluate_walk_forward, load_walk_forward_inputs)


REFERENCE_VARIANT = f"{VARIANT}_warmup120"
TRIAL_LOG = "outputs/experiments/reference_120_trials.jsonl"
WALK_FORWARD_RESULT_NAMES = ("walk_forward_120_summary", "walk_forward_120_predictions",
                             "walk_forward_120_metrics", "walk_forward_120_coefficients")
CPCV_RESULT_NAMES = ("cpcv_120_predictions", "cpcv_120_monthly", "cpcv_120_metrics", "cpcv_120_coefficients")
RESULT_NAMES = (*WALK_FORWARD_RESULT_NAMES, *CPCV_RESULT_NAMES)
TEST_INTERVAL = [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"]


def run_regime_reference(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    """Ajustar la misma logística en ambos calendarios y registrar una variante por regla."""
    from tfm.data import read_result

    samples, labels, preparation = load_walk_forward_inputs(root, min_history=REGIME_MIN_HISTORY)
    splits, split_report = read_result(root, REGIME_RESULT_NAMES[0])
    saved_summary, _ = read_result(root, REGIME_RESULT_NAMES[1])
    coverage = summarize_validation(splits, samples, calendar_start=REGIME_CPCV_START)
    try:
        pd.testing.assert_frame_equal(saved_summary, coverage, check_exact=True)
    except AssertionError as exc:
        raise ValueError("El resumen CPCV no corresponde a las entradas actuales; ejecuta el notebook 10.") from exc

    record = {"attempt": datetime.now(timezone.utc).isoformat(), "variant": REFERENCE_VARIANT,
              "candidate": "Logística M1 · 120 meses", "purpose": "reference_before_adding_regime",
              "candidate_configurations_per_rule": 1, "strategies": list(RULES),
              "validation_schemes": ["walk_forward", "CPCV"], "test_interval": TEST_INTERVAL,
              "min_history": REGIME_MIN_HISTORY, "target": "label", "model_columns": SIGNAL_COLUMNS,
              "model_parameters": MODEL_PARAMETERS, "parameters": labels["parameters"],
              "development": [split_report["development_start"], split_report["development_end"]],
              "cpcv_interval": [split_report["cpcv_calendar_start"], split_report["cpcv_calendar_end"]],
              "guide_version": "2026-11-28"}
    path = root / TRIAL_LOG
    path.parent.mkdir(parents=True, exist_ok=True)

    def append(status, **details):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")

    append("started")
    try:
        walk, walk_report = evaluate_walk_forward(samples)
        cpcv, cpcv_diagnostics = evaluate_cpcv_candidate(samples, splits, "M1", calendar_start=REGIME_CPCV_START)
        walk_main = walk["walk_forward_metrics"].loc[lambda t: t.aggregation.eq("pooled")]
        cpcv_main = cpcv["metrics"].loc[lambda t: t.aggregation.isin(["monthly_mean", "common_period"])]
        complete = walk_main.status.eq("completed").all() and cpcv_main.status.eq("completed").all()
        status = "completed" if complete else "incomplete"
        append(status, metrics={"walk_forward": json.loads(walk_main.to_json(orient="records")),
                                "CPCV": json.loads(cpcv_main.to_json(orient="records"))})
    except (Exception, KeyboardInterrupt) as exc:
        append("failed", error=str(exc))
        raise

    tables = dict(zip(WALK_FORWARD_RESULT_NAMES, (walk["walk_forward_summary"], walk["walk_forward_predictions"],
                                                 walk["walk_forward_metrics"], walk["walk_forward_coefficients"]), strict=True))
    tables.update(zip(CPCV_RESULT_NAMES, (cpcv["predictions"], cpcv["monthly"], cpcv["metrics"], cpcv["coefficients"]), strict=True))
    report = {**record, "scope": "development_m0_m1_reference_120", "experiment_status": status,
              "trial_log": TRIAL_LOG, "protocol": "docs/validacion_walk_forward.md#referencia-m0m1-con-120-meses",
              "sample_counts": preparation["sample_counts"], "first_causal_target": preparation["first_causal_target"],
              "causal_common_months": preparation["causal_common_months"], "purge_months": split_report["purge_months"],
              "cpcv_embargo_months": split_report["embargo_months"], "cpcv_blocks": split_report["blocks"],
              "walk_forward_diagnostics": walk_report["diagnostics"], "cpcv_diagnostics": cpcv_diagnostics,
              "versions": walk_report["versions"]}
    return tables, report
