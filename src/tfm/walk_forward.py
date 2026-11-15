"""Referencia cronológica de desarrollo, sin selección ni variables de régimen.

Protocolo: docs/validacion_walk_forward.md. Modelos M0/M1 del notebook 14.
No usa predicciones CPCV ni datos desde 1990.
"""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.diagnostics import START, END
from tfm.logistic import MODEL_PARAMETERS, _sklearn, fit_partition
from tfm.screening import RULES
from tfm.validation import MODEL_COLUMNS, PURGE_MONTHS, prepare_validation_samples


FIRST_TEST_YEAR, LAST_TEST_YEAR = 1950, 1989
SIGNAL_COLUMNS = ["z_price_return_1m", "z_momentum_12_1"]
VARIANT = "walk_forward_logistic_l2_C1_signal2_central"
RESULT_NAMES = ("walk_forward_splits", "walk_forward_summary", "walk_forward_predictions",
                "walk_forward_metrics", "walk_forward_coefficients")


def build_walk_forward_splits() -> pd.DataFrame:
    """Cuarenta años de prueba; purgar diciembre previo antes de filtrar ejemplos."""
    months = pd.period_range(START, END, freq="M")
    frames = []
    for split_id, year in enumerate(range(FIRST_TEST_YEAR, LAST_TEST_YEAR + 1), 1):
        start, end = pd.Period(f"{year}-01", freq="M"), pd.Period(f"{year}-12", freq="M")
        roles = np.full(len(months), "future", dtype=object)
        roles[months < start - PURGE_MONTHS] = "train"
        roles[(months >= start - PURGE_MONTHS) & (months < start)] = "purge"
        roles[(months >= start) & (months <= end)] = "validation"
        frames.append(pd.DataFrame({"split_id": split_id, "test_year": year,
                                    "target_period": months.astype(str), "role": roles}))
    return pd.concat(frames, ignore_index=True)


def load_walk_forward_inputs(root: Path) -> tuple[pd.DataFrame, dict, dict]:
    """Reconstruir la muestra común del desarrollo sin requerir los notebooks 09–13."""
    from tfm.data import read_result

    features, _ = read_result(root, "monthly_features")
    labels, label_report = read_result(root, "labelled_signals")
    samples, preparation = prepare_validation_samples(features, labels)
    return samples, label_report, preparation


def summarize_walk_forward(samples: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """Contar clases y ejemplos; una fila por año y regla aunque no haya señales."""
    pd.testing.assert_frame_equal(splits, build_walk_forward_splits(), check_exact=True)
    months = pd.period_range(START, END, freq="M").astype(str).tolist()
    if (set(samples.strategy) != set(RULES) or len(samples) != len(months) * len(RULES)
            or not samples.label_end_period.equals(samples.target_period)):
        raise ValueError("Se requiere el calendario de etiquetas mensuales de 1927–1989.")
    for flag in ("sample_usable", "causal_features_ready", "has_signal"):
        if not pd.api.types.is_bool_dtype(samples[flag]) or samples[flag].isna().any():
            raise ValueError("Las marcas de disponibilidad deben ser booleanas y completas.")
    if not samples.sample_usable.equals(samples.causal_features_ready & samples.has_signal):
        raise ValueError("La muestra común no corresponde a las características y señales.")
    for rule in RULES:
        if samples.loc[samples.strategy.eq(rule), "target_period"].tolist() != months:
            raise ValueError("Faltan meses o están duplicados/desordenados en la muestra.")
    if (not samples.label.isna().equals(~samples.has_signal)
            or not samples.loc[samples.has_signal, "label"].isin([0, 1]).all()
            or not np.isfinite(samples.loc[samples.sample_usable, MODEL_COLUMNS].to_numpy(dtype=float)).all()):
        raise ValueError("Los ejemplos necesitan etiqueta binaria y las diez características finitas.")
    records = []
    for (split_id, year), calendar in splits.groupby(["split_id", "test_year"], sort=True):
        for rule in RULES:
            rows = samples.loc[samples.strategy.eq(rule)].merge(
                calendar[["target_period", "role"]], on="target_period", validate="one_to_one")
            train = rows.loc[rows.role.eq("train") & rows.sample_usable]
            validation = rows.loc[rows.role.eq("validation")]
            usable = validation.loc[validation.sample_usable]
            records.append({"split_id": int(split_id), "test_year": int(year), "strategy": rule,
                "train_calendar_months": int(rows.role.eq("train").sum()),
                "train_first_target": str(train.target_period.iloc[0]) if len(train) else None,
                "train_last_target": str(train.target_period.iloc[-1]) if len(train) else None,
                "train_examples": len(train), "train_positive": int(train.label.eq(1).sum()),
                "train_classes": int(train.label.nunique()),
                "purge_calendar_months": int(rows.role.eq("purge").sum()),
                "validation_calendar_months": len(validation),
                "no_signal_months": int((~validation.has_signal).sum()),
                "excluded_active_months": int((validation.has_signal & ~validation.sample_usable).sum()),
                "validation_examples": len(usable), "validation_positive": int(usable.label.eq(1).sum()),
                "validation_classes": int(usable.label.nunique())})
    return pd.DataFrame(records)


def summarize_walk_forward_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Una predicción por ejemplo; conservar los 80 años/reglas y cuatro totales."""
    _, _, log_loss, roc_auc_score = _sklearn()
    if (predictions.duplicated(["strategy", "target_period"]).any()
            or not predictions.label.isin([0, 1]).all()
            or not set(predictions.strategy) <= set(RULES)):
        raise ValueError("Predicciones duplicadas, reglas desconocidas o etiquetas no binarias.")
    if len(predictions):
        targets = pd.PeriodIndex(predictions.target_period, freq="M")
        if (predictions.target_period.tolist() != targets.astype(str).tolist()
                or not np.array_equal(predictions.test_year.to_numpy(), targets.year)
                or not np.array_equal(predictions.split_id.to_numpy(), targets.year - FIRST_TEST_YEAR + 1)
                or not ((targets.year >= FIRST_TEST_YEAR) & (targets.year <= LAST_TEST_YEAR)).all()):
            raise ValueError("Las predicciones no corresponden al año de prueba fijado.")
    for column in ("probability_logistic", "probability_naive"):
        values = predictions[column].dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError("Las probabilidades deben estar entre cero y uno o quedar ausentes.")
    observed = {(int(split), rule): rows for (split, rule), rows in
                predictions.groupby(["split_id", "strategy"], sort=True)}
    empty = predictions.iloc[:0]
    groups = [("year", split, year, rule, observed.get((split, rule), empty))
              for split, year in enumerate(range(FIRST_TEST_YEAR, LAST_TEST_YEAR + 1), 1) for rule in RULES]
    groups += [("pooled", None, None, rule, predictions.loc[predictions.strategy.eq(rule)]) for rule in RULES]
    records = []
    for aggregation, split, year, rule, rows in groups:
        for model, column in (("M0", "probability_naive"), ("M1", "probability_logistic")):
            y = rows.label.to_numpy(dtype=int)
            p = rows[column].to_numpy(dtype=float)
            complete = bool(len(y) and np.isfinite(p).all())
            two_classes = len(np.unique(y)) == 2
            records.append({"aggregation": aggregation, "split_id": split, "test_year": year,
                "strategy": rule, "model": model, "examples": len(y), "positive": int(y.sum()),
                "negative": int(len(y) - y.sum()),
                "status": "empty_validation" if not len(y) else "completed" if complete else "unavailable_predictions",
                "auc_status": ("no_examples" if not len(y) else "unavailable_predictions" if not complete
                               else "available" if two_classes else "single_class"),
                "log_loss": float(log_loss(y, p, labels=[0, 1])) if complete else None,
                "auc": float(roc_auc_score(y, p)) if complete and two_classes else None})
    metrics = pd.DataFrame(records)
    for column in ("split_id", "test_year"):
        metrics[column] = metrics[column].astype("Int64")
    return metrics


def evaluate_walk_forward(samples: pd.DataFrame, *, progress=None) -> tuple[dict, dict]:
    splits = build_walk_forward_splits()
    coverage = summarize_walk_forward(samples, splits)
    predictions, coefficients, diagnostics = [], [], []
    for (split_id, year), calendar in splits.groupby(["split_id", "test_year"], sort=True):
        for rule in RULES:
            rows = samples.loc[samples.strategy.eq(rule) & samples.sample_usable].merge(
                calendar[["target_period", "role"]], on="target_period", validate="one_to_one")
            p, c, d = fit_partition(rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")],
                                    strategy=rule, split_id=int(split_id), columns=SIGNAL_COLUMNS)
            p.insert(1, "test_year", int(year))
            c.insert(1, "test_year", int(year))
            predictions.append(p)
            coefficients.append(c)
            diagnostics.append({**d, "test_year": int(year)})
        if progress:
            progress(int(split_id), LAST_TEST_YEAR - FIRST_TEST_YEAR + 1)
    predictions = pd.concat(predictions, ignore_index=True)
    expected = samples.loc[samples.sample_usable & samples.target_period.between(
        f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"), ["strategy", "target_period", "label"]]
    pd.testing.assert_frame_equal(predictions[expected.columns].sort_values(["strategy", "target_period"]).reset_index(drop=True),
                                  expected.sort_values(["strategy", "target_period"]).reset_index(drop=True), check_exact=True)
    metrics = summarize_walk_forward_predictions(predictions)
    diagnostic = pd.DataFrame(diagnostics)
    coverage = coverage.merge(diagnostic[["split_id", "strategy", "iterations", "status"]],
                               on=["split_id", "strategy"], validate="one_to_one")
    tables = dict(zip(RESULT_NAMES, [splits, coverage, predictions, metrics,
                                   pd.concat(coefficients, ignore_index=True)]))
    report = {"scope": "development_walk_forward_signal_reference", "variant": VARIANT,
        "models": {"M0": "positive label frequency of annual training", "M1": "logistic L2 with two signal features"},
        "model_columns": SIGNAL_COLUMNS, "model_parameters": MODEL_PARAMETERS, "target": "label",
        "development": [START, END], "test_interval": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"],
        "window": "expanding", "refit": "annual; coefficients fixed throughout each test year",
        "annual_test_folds": LAST_TEST_YEAR - FIRST_TEST_YEAR + 1, "purge_months": PURGE_MONTHS,
        "embargo": "not applicable: there is no training after the current validation interval",
        "common_sample": "same ten-feature availability and causal warmup as 10–13; only two columns predict",
        "aggregation": "one chronological out-of-sample prediction per active usable example; pooled AUC/log-loss",
        "skill_gate_status": "pending_regime_comparisons_shadows_and_economic_evaluation",
        "diagnostics": diagnostics, "guide_version": "2026-11-15",
        "versions": {name: version(name) for name in ("scikit-learn", "numpy", "pandas")},
        "warnings": ["Design fixed after the earlier ten-feature CPCV experiments, not before all exploration.",
                     "No regime acceptance, model selection, SHAP, economic simulation, DSR/PBO or post-1989 evaluation.",
                     "Shiller means are not executable closes; reconstructed dividends and source revisions are not certified point-in-time.",
                     "Purging the previous target month does not certify historical publication dates of labels.",
                     "Signal-only is an operational baseline; signal features can indirectly describe market conditions.",
                     "Annual AUC is undefined with zero or one label class; those years remain in all tables."]}
    return tables, report


def run_walk_forward(root: Path, *, progress=None) -> tuple[dict, dict]:
    samples, label_report, preparation = load_walk_forward_inputs(root)
    attempt = datetime.now(timezone.utc).isoformat()
    record = {"attempt": attempt, "variant": VARIANT, "purpose": "chronological_signal_reference",
        "candidate_configurations_per_rule": 1, "strategies": list(RULES), "target": "label",
        "model_columns": SIGNAL_COLUMNS, "model_parameters": MODEL_PARAMETERS,
        "parameters": label_report["parameters"], "development": [START, END],
        "test_years": [FIRST_TEST_YEAR, LAST_TEST_YEAR], "purge_months": PURGE_MONTHS,
        "window": "expanding", "refit": "annual", "guide_version": "2026-11-15"}
    path = root / "outputs/experiments/walk_forward_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    def append(event):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False) + "\n")

    append({"status": "started"})
    try:
        tables, report = evaluate_walk_forward(samples, progress=progress)
        main = tables["walk_forward_metrics"].loc[lambda t: t.aggregation.eq("pooled")]
        status = "completed" if main.status.eq("completed").all() else "incomplete"
        append({"status": status, "metrics": json.loads(main.to_json(orient="records"))})
    except (Exception, KeyboardInterrupt) as exc:
        append({"status": "failed", "error": str(exc)})
        raise
    report.update(parameters=label_report["parameters"], sample_counts=preparation["sample_counts"],
                  attempt=attempt, experiment_status=status, trial_log="outputs/experiments/walk_forward_trials.jsonl",
                  protocol="docs/validacion_walk_forward.md")
    return tables, report
