"""M2 con los compuestos de cada entrenamiento y comparación emparejada con M1."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.cpcv_regime import _common_period_metrics, compare_cpcv_models
from tfm.features import REGIME_FAMILIES
from tfm.logistic import MODEL_PARAMETERS, fit_partition, summarize_predictions
from tfm.regime_compounds import RESULT_NAMES as COMPOUND_RESULTS
from tfm.regime_reference import (CPCV_RESULT_NAMES, REFERENCE_VARIANT, TEST_INTERVAL, WALK_FORWARD_RESULT_NAMES)
from tfm.screening import REGIME_MIN_HISTORY, RULES
from tfm.validation import REGIME_RESULT_NAMES
from tfm.walk_forward import (SIGNAL_COLUMNS, build_walk_forward_splits, compare_walk_forward_models,
                              load_walk_forward_inputs, summarize_walk_forward_predictions)


VARIANT = "logistic_l2_C1_signal2_compounds_central_warmup120"
TRIAL_LOG = "outputs/experiments/compounds_m2_trials.jsonl"
RESULT_NAMES = ("regime_120_m2_predictions", "regime_120_m2_comparison", "regime_120_m2_coefficients")
KEYS = ["split_id", "strategy", "target_period"]


def fit_m2_partitions(samples: pd.DataFrame, calendar: pd.DataFrame, compounds: pd.DataFrame,
                      reference: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Ajustar con las familias disponibles en train y conservar la referencia exacta si faltan todas."""
    dates = calendar.loc[calendar.role.isin(["train", "validation"]), ["split_id", "target_period", "role"]]
    usable = samples.loc[samples.sample_usable, ["strategy", "target_period", "label", *SIGNAL_COLUMNS]]
    rows = dates.merge(usable, on="target_period", validate="many_to_many").merge(
        compounds[[*KEYS, "role", *REGIME_FAMILIES]], on=[*KEYS, "role"], how="left",
        indicator=True, validate="one_to_one")
    if not rows._merge.eq("both").all():
        raise ValueError("Faltan compuestos para el calendario de M2; repite su preparación en el notebook 14.")
    expected = rows.loc[rows.role.eq("validation"), [*KEYS, "label"]].sort_values(KEYS).reset_index(drop=True)
    reference = reference.sort_values(KEYS).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(reference[expected.columns], expected, check_exact=True)
    except AssertionError as exc:
        raise ValueError("Las señales y etiquetas deben coincidir con la referencia M1 de 120 meses.") from exc
    if not reference.probability_m1.between(0, 1).all():
        raise ValueError("Faltan probabilidades válidas de M1 para emparejar la comparación.")

    coefficients, diagnostics, predictions = [], [], []
    for split_id in calendar.split_id.unique():
        for rule in RULES:
            part = rows.loc[rows.split_id.eq(split_id) & rows.strategy.eq(rule)].sort_values("target_period")
            train = part.loc[part.role.eq("train")]
            test = part.loc[part.role.eq("validation")]
            family_columns = [name for name in REGIME_FAMILIES if train[name].notna().any()]
            expected_presence = [name in family_columns for name in REGIME_FAMILIES]
            if not (part[list(REGIME_FAMILIES)].notna().to_numpy() == expected_presence).all():
                raise ValueError("La disponibilidad de los compuestos debe ser constante dentro de cada entrenamiento y prueba.")
            paired = reference.loc[reference.split_id.eq(split_id) & reference.strategy.eq(rule)].copy()
            if family_columns:
                fitted, terms, diagnostic = fit_partition(train, test, strategy=rule, split_id=int(split_id),
                                                          columns=[*SIGNAL_COLUMNS, *family_columns])
                paired["probability_m2"] = fitted.probability_logistic.to_numpy()
                coefficients.append(terms)
                iterations, status = diagnostic["iterations"], diagnostic["status"]
            else:
                paired["probability_m2"] = paired.probability_m1
                iterations, status = None, "reused_m1"
            paired["fit_status_m2"] = status
            predictions.append(paired)
            diagnostics.append({"split_id": int(split_id), "strategy": rule, "families": family_columns,
                                "train_examples": len(train), "validation_examples": len(test),
                                "iterations": iterations, "status": status})
    terms = pd.concat(coefficients, ignore_index=True) if coefficients else pd.DataFrame({
        "split_id": pd.Series(dtype=int), "strategy": pd.Series(dtype=str), "term": pd.Series(dtype=str),
        "coefficient": pd.Series(dtype=float), "fit_status": pd.Series(dtype=str)})
    return pd.concat(predictions, ignore_index=True), terms, diagnostics


def run_regime_m2(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    from tfm.data import read_result

    samples, labels, _ = load_walk_forward_inputs(root, min_history=REGIME_MIN_HISTORY)
    compounds, compound_info = read_result(root, COMPOUND_RESULTS[2])
    cpcv_splits, _ = read_result(root, REGIME_RESULT_NAMES[0])
    walk, walk_info = read_result(root, WALK_FORWARD_RESULT_NAMES[1])
    cpcv, cpcv_info = read_result(root, CPCV_RESULT_NAMES[0])
    versions = {name: version(name) for name in ("scikit-learn", "numpy", "pandas")}
    if (not walk_info.get("attempt") or walk_info["attempt"] != cpcv_info.get("attempt")
            or any(info.get("variant") != REFERENCE_VARIANT or info.get("experiment_status") != "completed"
                   or info.get("model_parameters") != MODEL_PARAMETERS or info.get("min_history") != REGIME_MIN_HISTORY
                   or info.get("parameters") != labels["parameters"] or info.get("versions") != versions
                   for info in (walk_info, cpcv_info))):
        raise ValueError("Ejecuta la referencia M0/M1 con 120 meses del notebook 14 para los dos recorridos.")
    if (compound_info.get("parameters") != labels["parameters"] or compound_info.get("min_history") != REGIME_MIN_HISTORY
            or compound_info.get("families") != {name: list(columns) for name, columns in REGIME_FAMILIES.items()}):
        raise ValueError("Los compuestos deben corresponder al protocolo de 120 meses y a los costes actuales.")

    record = {"attempt": datetime.now(timezone.utc).isoformat(), "variant": VARIANT,
              "candidate": "Logística M2 · compuestos · 120 meses", "candidate_configurations_per_rule": 1,
              "strategies": list(RULES), "validation_schemes": ["walk_forward", "CPCV"], "test_interval": TEST_INTERVAL,
              "reference_attempt": walk_info["attempt"], "min_history": REGIME_MIN_HISTORY,
              "model_parameters": MODEL_PARAMETERS, "parameters": labels["parameters"], "target": "label",
              "guide_version": "2026-11-28", "versions": versions}
    path = root / TRIAL_LOG
    path.parent.mkdir(parents=True, exist_ok=True)

    def append(status, **details):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, "status": status, **details}, ensure_ascii=False, allow_nan=False) + "\n")

    append("started")
    try:
        walk_ref = walk[[*KEYS, "label", "probability_logistic"]].rename(columns={"probability_logistic": "probability_m1"})
        cpcv_ref = cpcv[[*KEYS, "label", "probability_model"]].rename(columns={"probability_model": "probability_m1"})
        walk_pred, walk_terms, walk_diagnostics = fit_m2_partitions(samples, build_walk_forward_splits(),
            compounds.loc[compounds.validation_scheme.eq("walk_forward")], walk_ref)
        cpcv_pred, cpcv_terms, cpcv_diagnostics = fit_m2_partitions(samples, cpcv_splits,
            compounds.loc[compounds.validation_scheme.eq("CPCV")], cpcv_ref)
        walk_pred["test_year"] = walk_pred.target_period.str[:4].astype("Int64")
        cpcv_pred["test_year"] = pd.Series(pd.NA, index=cpcv_pred.index, dtype="Int64")
        walk_metrics = summarize_walk_forward_predictions(walk_pred, models={"M1": "probability_m1", "M2": "probability_m2"})
        walk_comparison, walk_stability = compare_walk_forward_models(walk_metrics, [("M1", "M2")])
        cpcv_input = cpcv_pred.rename(columns={"probability_m1": "probability_naive", "probability_m2": "probability_logistic"})
        monthly, metrics = summarize_predictions(cpcv_input, partitions=pd.DataFrame(cpcv_diagnostics))
        metrics = pd.concat([metrics, _common_period_metrics(monthly)], ignore_index=True)
        metrics["model"] = metrics.model.map({"naive": "M1", "logistic": "M2"})
        cpcv_comparison, cpcv_stability = compare_cpcv_models(metrics, pairs=[("M1", "M2", None)])
        cpcv_comparison["test_year"] = pd.Series(pd.NA, index=cpcv_comparison.index, dtype="Int64")
        comparison = pd.concat([walk_comparison.assign(validation_scheme="walk_forward"),
                                cpcv_comparison.drop(columns="removed_feature").assign(validation_scheme="CPCV")], ignore_index=True)
        main = comparison.loc[comparison.aggregation.isin(["pooled", "monthly_mean", "common_period"])]
        status = "completed" if main.comparison_status.eq("available").all() else "incomplete"
        append(status, comparison=json.loads(main.to_json(orient="records")))
    except (Exception, KeyboardInterrupt) as exc:
        append("failed", error=str(exc))
        raise

    predictions = pd.concat([walk_pred.assign(validation_scheme="walk_forward"),
                             cpcv_pred.assign(validation_scheme="CPCV")], ignore_index=True)
    terms = pd.concat([walk_terms.assign(validation_scheme="walk_forward"),
                       cpcv_terms.assign(validation_scheme="CPCV")], ignore_index=True)
    report = {**record, "experiment_status": status, "scope": "development_m2_compounds_prediction_comparison",
              "trial_log": TRIAL_LOG, "walk_forward_diagnostics": walk_diagnostics, "cpcv_diagnostics": cpcv_diagnostics,
              "walk_forward_stability": walk_stability, "cpcv_stability": cpcv_stability,
              "protocol": "docs/validacion_walk_forward.md#m2-con-compuestos-de-régimen"}
    return dict(zip(RESULT_NAMES, (predictions, comparison, terms), strict=True)), report
