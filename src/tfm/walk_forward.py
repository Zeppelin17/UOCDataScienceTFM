"""Comparación cronológica de desarrollo, con listas fijas de características.

Protocolo: docs/validacion_walk_forward.md. Modelos M0/M1/M2 del notebook 14.
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
REGIME_COLUMNS = ["z_price_volatility_12m", "z_market_return_24m", "z_drawdown_12m"]
M2_COLUMNS = [*SIGNAL_COLUMNS, *REGIME_COLUMNS]
VARIANT = "walk_forward_logistic_l2_C1_signal2_central"
REGIME_VARIANT = "walk_forward_logistic_l2_C1_signal2_regime3_central"
RESULT_NAMES = ("walk_forward_splits", "walk_forward_summary", "walk_forward_predictions",
                "walk_forward_metrics", "walk_forward_coefficients")
REGIME_RESULTS = ("walk_forward_regime_predictions", "walk_forward_regime_metrics",
                  "walk_forward_regime_coefficients", "walk_forward_regime_comparison")


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


def summarize_walk_forward_predictions(predictions: pd.DataFrame, *,
                                       models: dict[str, str] | None = None) -> pd.DataFrame:
    """Una predicción por ejemplo; conservar los 80 años/reglas para cada modelo."""
    _, _, log_loss, roc_auc_score = _sklearn()
    models = {"M0": "probability_naive", "M1": "probability_logistic"} if models is None else models
    if not models or len(set(models.values())) != len(models):
        raise ValueError("Se requieren modelos con columnas de probabilidad distintas.")
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
    for column in models.values():
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
        for model, column in models.items():
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


def load_walk_forward_reference(root: Path, samples: pd.DataFrame,
                                label_report: dict) -> tuple[dict, dict]:
    """Leer y contrastar M0/M1 antes de añadir régimen, sin volver a ajustarlos."""
    from tfm.data import read_result

    stored = {name: read_result(root, name) for name in RESULT_NAMES}
    report = stored["walk_forward_metrics"][1]
    versions = {name: version(name) for name in ("scikit-learn", "numpy", "pandas")}
    if (report.get("variant") != VARIANT or report.get("model_columns") != SIGNAL_COLUMNS
            or report.get("model_parameters") != MODEL_PARAMETERS or report.get("target") != "label"
            or report.get("parameters") != label_report["parameters"] or report.get("versions") != versions
            or report.get("test_interval") != [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"]
            or report.get("window") != "expanding" or report.get("purge_months") != PURGE_MONTHS
            or report.get("experiment_status") != "completed" or not report.get("attempt")
            or any(info.get("attempt") != report["attempt"] for _, info in stored.values())):
        raise ValueError("Ejecuta primero la parte M0/M1 del notebook 14 con las entradas y el entorno actuales.")
    tables = {name: table for name, (table, _) in stored.items()}
    try:
        coverage = summarize_walk_forward(samples, tables["walk_forward_splits"])
        pd.testing.assert_frame_equal(coverage, tables["walk_forward_summary"][coverage.columns], check_exact=True)
        predictions = tables["walk_forward_predictions"]
        expected = samples.loc[samples.sample_usable & samples.target_period.between(
            f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"), ["strategy", "target_period", "label"]]
        keys = ["strategy", "target_period"]
        pd.testing.assert_frame_equal(predictions[expected.columns].sort_values(keys).reset_index(drop=True),
                                      expected.sort_values(keys).reset_index(drop=True), check_exact=True)
        pd.testing.assert_frame_equal(summarize_walk_forward_predictions(predictions),
                                      tables["walk_forward_metrics"], check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("La referencia no corresponde a los ejemplos actuales; repite la parte M0/M1 del notebook 14.") from exc
    return tables, report


def compare_walk_forward_regime(reference: pd.DataFrame, regime: pd.DataFrame) -> pd.DataFrame:
    """Diferencias emparejadas, sin omitir años con una clase o predicciones ausentes."""
    keys = ["aggregation", "split_id", "test_year", "strategy"]
    columns = [*keys, "examples", "positive", "negative", "status", "auc", "log_loss"]
    m1 = reference.loc[reference.model.eq("M1"), columns]
    m2 = regime.loc[regime.model.eq("M2"), columns]
    compared = m1.merge(m2, on=keys, how="outer", validate="one_to_one", suffixes=("_m1", "_m2"), indicator=True)
    if (len(compared) != (LAST_TEST_YEAR-FIRST_TEST_YEAR+2)*len(RULES)
            or not compared._merge.eq("both").all()
            or any(not compared[f"{name}_m1"].equals(compared[f"{name}_m2"])
                   for name in ("examples", "positive", "negative"))):
        raise ValueError("M1 y M2 deben evaluar los mismos ejemplos, clases y periodos.")
    available = (compared.status_m1.eq("completed") & compared.status_m2.eq("completed"))
    loss_available = available & np.isfinite(compared[["log_loss_m1", "log_loss_m2"]].to_numpy(dtype=float)).all(axis=1)
    auc_available = available & np.isfinite(compared[["auc_m1", "auc_m2"]].to_numpy(dtype=float)).all(axis=1)
    compared["log_loss_improvement"] = (compared.log_loss_m1 - compared.log_loss_m2).where(loss_available)
    compared["auc_improvement"] = (compared.auc_m2 - compared.auc_m1).where(auc_available)
    compared["auc_improved"] = compared.auc_improvement.gt(0).astype("boolean").where(auc_available)
    compared["comparison_status"] = np.select(
        [compared.examples_m1.eq(0), ~available, ~auc_available],
        ["empty_validation", "unavailable_predictions", "single_class"], default="available")
    compared = compared.drop(columns=["_merge", "examples_m2", "positive_m2", "negative_m2"]).rename(
        columns={"examples_m1": "examples", "positive_m1": "positive", "negative_m1": "negative"})
    # Mantener el orden cronológico del resumen, con los dos totales al final.
    return compared.sort_values(["aggregation", "split_id", "strategy"], ascending=[False, True, True],
                                 na_position="last").reset_index(drop=True)


def evaluate_walk_forward_regime(samples: pd.DataFrame, reference_predictions: pd.DataFrame,
                                 *, progress=None) -> tuple[dict, dict]:
    splits = build_walk_forward_splits()
    coverage = summarize_walk_forward(samples, splits)
    reference_metrics = summarize_walk_forward_predictions(reference_predictions)
    pieces, coefficients, diagnostics = [], [], []
    for (split_id, year), calendar in splits.groupby(["split_id", "test_year"], sort=True):
        for rule in RULES:
            rows = samples.loc[samples.strategy.eq(rule) & samples.sample_usable].merge(
                calendar[["target_period", "role"]], on="target_period", validate="one_to_one")
            p, c, d = fit_partition(rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")],
                                    strategy=rule, split_id=int(split_id), columns=M2_COLUMNS)
            p.insert(1, "test_year", int(year))
            c.insert(1, "test_year", int(year))
            pieces.append(p.rename(columns={"probability_logistic": "probability_regime", "fit_status": "fit_status_regime"}))
            coefficients.append(c)
            diagnostics.append({**d, "test_year": int(year)})
        if progress:
            progress(int(split_id), LAST_TEST_YEAR - FIRST_TEST_YEAR + 1)
    regime = pd.concat(pieces, ignore_index=True)
    keys = ["split_id", "test_year", "strategy", "target_period", "label"]
    checked = [*keys, "probability_naive"]
    try:
        pd.testing.assert_frame_equal(reference_predictions[checked].sort_values(keys[:4]).reset_index(drop=True),
                                      regime[checked].sort_values(keys[:4]).reset_index(drop=True), check_exact=True)
    except AssertionError as exc:
        raise ValueError("M2 no comparte exactamente las fechas, etiquetas y referencia ingenua de M1.") from exc
    predictions = reference_predictions.merge(regime.drop(columns="probability_naive"), on=keys,
                                               how="left", validate="one_to_one")
    metrics = summarize_walk_forward_predictions(predictions, models={"M2": "probability_regime"})
    comparison = compare_walk_forward_regime(reference_metrics, metrics)
    stability = []
    for rule in RULES:
        annual = comparison.loc[comparison.aggregation.eq("year") & comparison.strategy.eq(rule)]
        expected = LAST_TEST_YEAR - FIRST_TEST_YEAR + 1
        if len(annual) != expected:
            raise ValueError("La comparación debe conservar todos los años previstos.")
        improved = int(annual.auc_improved.fillna(False).sum())
        stability.append({"strategy": rule, "expected_years": expected,
            "auc_available_years": int(annual.comparison_status.eq("available").sum()),
            "auc_improved_years": improved, "auc_worsened_years": int(annual.auc_improvement.lt(0).sum()),
            "auc_tied_years": int(annual.auc_improvement.eq(0).sum()),
            "auc_unavailable_years": int(annual.auc_improved.isna().sum()),
            "majority_required": expected//2+1, "meets_majority": improved > expected/2})
    tables = dict(zip(REGIME_RESULTS, [predictions, metrics, pd.concat(coefficients, ignore_index=True), comparison]))
    report = {"scope": "development_walk_forward_direct_regime_comparison", "variant": REGIME_VARIANT,
        "reference_variant": VARIANT, "model_columns": M2_COLUMNS, "regime_columns": REGIME_COLUMNS,
        "model_parameters": MODEL_PARAMETERS, "target": "label", "guide_version": "2026-11-15",
        "development": [START, END], "test_interval": [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"],
        "window": "expanding", "refit": "annual", "purge_months": PURGE_MONTHS,
        "sample_counts": coverage.groupby("strategy").validation_examples.sum().to_dict(),
        "comparison": "same examples and training; pooled AUC(M2)-AUC(M1); fixed five predictors, no selection",
        "skill_gate_status": "pending_matched_cpcv_regime_shadows_and_economic_evaluation",
        "diagnostics": diagnostics, "stability": stability,
        "versions": {name: version(name) for name in ("scikit-learn", "numpy", "pandas")},
        "warnings": ["This compares the three-regime-variable block, not each variable's incremental contribution.",
                     "Annual folds can be empty or single-class; unavailable AUC does not count as an improvement.",
                     "Pooled discrimination and annual stability alone do not accept the regime or establish profitability.",
                     "M3, individual removals, matched CPCV, regime shadows, SHAP and economic controls remain pending.",
                     "Monthly means, reconstructed dividends and source revisions retain their availability limitations."]}
    return tables, report


def run_walk_forward_regime(root: Path, *, progress=None) -> tuple[dict, dict]:
    """Añadir M2 leyendo la referencia publicada; registrar una nueva variante por regla."""
    samples, label_report, _ = load_walk_forward_inputs(root)
    reference, original_report = load_walk_forward_reference(root, samples, label_report)
    attempt = datetime.now(timezone.utc).isoformat()
    record = {"attempt": attempt, "variant": REGIME_VARIANT, "purpose": "direct_regime_comparison",
        "reference_variant": VARIANT, "reference_attempt": original_report["attempt"],
        "candidate_configurations_per_rule": 1, "strategies": list(RULES), "target": "label",
        "model_columns": M2_COLUMNS, "regime_columns": REGIME_COLUMNS, "model_parameters": MODEL_PARAMETERS,
        "parameters": label_report["parameters"], "development": [START, END],
        "test_years": [FIRST_TEST_YEAR, LAST_TEST_YEAR], "purge_months": PURGE_MONTHS,
        "window": "expanding", "refit": "annual", "guide_version": "2026-11-15"}
    path = root / "outputs/experiments/walk_forward_trials.jsonl"

    def append(event):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False) + "\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    append({"status": "started"})
    try:
        tables, report = evaluate_walk_forward_regime(samples, reference["walk_forward_predictions"], progress=progress)
        main = tables["walk_forward_regime_comparison"].loc[lambda t: t.aggregation.eq("pooled")]
        status = "completed" if main.comparison_status.eq("available").all() else "incomplete"
        append({"status": status, "comparison": json.loads(main.to_json(orient="records")), "stability": report["stability"]})
    except (Exception, KeyboardInterrupt) as exc:
        append({"status": "failed", "error": str(exc)})
        raise
    report.update(parameters=label_report["parameters"], attempt=attempt, reference_attempt=original_report["attempt"],
                  experiment_status=status, trial_log="outputs/experiments/walk_forward_trials.jsonl",
                  protocol="docs/validacion_walk_forward.md")
    return tables, report
