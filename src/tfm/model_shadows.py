"""Referencias circulares del clasificador L2, con el protocolo del notebook 12."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.logistic import (MODEL_PARAMETERS, VARIANT, evaluate_logistic,
                         load_logistic_inputs, summarize_predictions)
from tfm.screening import MIN_SHIFT, RULES
from tfm.validation import MODEL_COLUMNS, summarize_validation


RESULT_NAMES = ("logistic_shadows", "logistic_shadow_comparison")
SHADOW_QUANTILE = .95
QUANTILE_METHOD = "higher"
AUC_REFERENCE = .54


def model_calendar(samples: pd.DataFrame) -> pd.DataFrame:
    """Meses comunes, antes de retirar las señales de efectivo de cada regla."""
    parts = [samples.loc[samples.strategy.eq(rule) & samples.causal_features_ready,
                         ["target_period", *MODEL_COLUMNS]].reset_index(drop=True) for rule in RULES]
    first = parts[0]
    if (len(first) < 2 * MIN_SHIFT + 1
            or first.target_period.tolist() != pd.period_range(first.target_period.iloc[0],
                                                               first.target_period.iloc[-1], freq="M").astype(str).tolist()
            or not np.isfinite(first[MODEL_COLUMNS].to_numpy(dtype=float)).all()):
        raise ValueError("Las sombras necesitan un calendario común continuo con características finitas.")
    try:
        pd.testing.assert_frame_equal(first, parts[1], check_exact=True)
    except AssertionError as exc:
        raise ValueError("Ambas reglas deben compartir las mismas características por mes.") from exc
    return first


def circular_shifts(months: int) -> list[int]:
    if months < 2 * MIN_SHIFT + 1:
        raise ValueError("No hay meses suficientes para la separación circular de 36 meses.")
    return list(range(MIN_SHIFT, months - MIN_SHIFT + 1))


def circular_shadow(samples: pd.DataFrame, shift: int) -> pd.DataFrame:
    """Rotar solo las diez columnas, con la misma rotación para ambas reglas."""
    calendar = model_calendar(samples)
    if (isinstance(shift, bool) or not isinstance(shift, (int, np.integer))
            or shift < MIN_SHIFT or shift > len(calendar) - MIN_SHIFT):
        raise ValueError("Desplazamiento fuera de la distancia circular mínima de 36 meses.")
    moved = np.roll(calendar[MODEL_COLUMNS].to_numpy(dtype=float), shift, axis=0)
    shadow = samples.copy()
    for rule in RULES:
        mask = shadow.strategy.eq(rule) & shadow.causal_features_ready
        shadow.loc[mask, MODEL_COLUMNS] = moved
    return shadow


def _main_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    main = metrics.loc[metrics.aggregation.eq("monthly_mean")].copy()
    expected = {(rule, model) for rule in RULES for model in ("logistic", "naive")}
    if (main.duplicated(["strategy", "model"]).any()
            or set(zip(main.strategy, main.model)) != expected):
        raise ValueError("Se necesitan las métricas mensuales de ambos métodos y reglas.")
    return main


def compare_shadows(shadows: pd.DataFrame, original_metrics: pd.DataFrame,
                    expected_shifts: list[int]) -> tuple[pd.DataFrame, dict]:
    """No calcular umbrales con rotaciones ausentes, fallidas o incompletas."""
    expected = {(shift, rule) for shift in expected_shifts for rule in RULES}
    actual = set(zip(shadows.shift_months, shadows.strategy))
    if (not expected_shifts or len(set(expected_shifts)) != len(expected_shifts)
            or shadows.duplicated(["shift_months", "strategy"]).any() or not actual <= expected):
        raise ValueError("Las sombras deben ser únicas y pertenecer a los desplazamientos previstos.")
    finite = np.isfinite(shadows[["log_loss", "auc", "log_loss_improvement"]].to_numpy(dtype=float)).all(axis=1)
    available = bool(actual == expected and shadows.status.eq("completed").all() and finite.all())
    main = _main_metrics(original_metrics)
    records = []
    for rule in RULES:
        original = main.loc[main.strategy.eq(rule)].set_index("model")
        real = original.loc["logistic"]
        naive = original.loc["naive"]
        improvement = float(naive.log_loss - real.log_loss)
        valid_original = (original.status.eq("completed").all()
                          and np.isfinite([real.log_loss, real.auc, naive.log_loss]).all())
        usable = bool(available and valid_original)
        rows = shadows.loc[shadows.strategy.eq(rule)]
        threshold = float(np.quantile(rows.log_loss_improvement, SHADOW_QUANTILE,
                                       method=QUANTILE_METHOD)) if usable else None
        auc_threshold = float(np.quantile(rows.auc, SHADOW_QUANTILE, method=QUANTILE_METHOD)) if usable else None
        auc_met = bool(real.auc >= AUC_REFERENCE) if valid_original else None
        beats_naive = bool(improvement > 0) if valid_original else None
        exceeds = bool(improvement > threshold) if usable else None
        meets = bool(auc_met and beats_naive and exceeds) if usable else None
        records.append({"strategy": rule, "examples": int(real.examples),
                        "original_log_loss": float(real.log_loss), "naive_log_loss": float(naive.log_loss),
                        "original_auc": float(real.auc), "original_improvement": improvement,
                        "expected_shadows": len(expected_shifts), "completed_shadows": int((rows.status.eq("completed")
                            & np.isfinite(rows[["log_loss", "auc", "log_loss_improvement"]].to_numpy(dtype=float)).all(axis=1)).sum()),
                        "comparison_available": usable, "improvement_threshold_95": threshold,
                        "auc_threshold_95_descriptive": auc_threshold,
                        "fraction_shadows_below_original_improvement": float(rows.log_loss_improvement.lt(improvement).mean()) if usable else None,
                        "fraction_shadows_below_original_auc": float(rows.auc.lt(real.auc).mean()) if usable else None,
                        "auc_at_least_054": auc_met, "beats_naive_log_loss": beats_naive,
                        "exceeds_shadow_threshold": exceeds, "meets_operational_criterion": meets,
                        "status": ("unavailable" if not usable else "meets_criterion" if meets else "does_not_meet_criterion")})
    comparison = pd.DataFrame(records)
    for name in ("auc_at_least_054", "beats_naive_log_loss", "exceeds_shadow_threshold", "meets_operational_criterion"):
        comparison[name] = comparison[name].astype("boolean")
    return comparison, {"shadow_comparison_available": bool(comparison.comparison_available.all()),
                        "expected_shadows": len(expected_shifts), "expected_shadow_rows": len(expected),
                        "missing_shadow_rows": len(expected - actual),
                        "invalid_shadow_rows": int((~shadows.status.eq("completed") | ~finite).sum())}


def _load_original(root: Path, samples: pd.DataFrame, splits: pd.DataFrame,
                   label_report: dict) -> tuple[pd.DataFrame, dict]:
    """Contrastar las salidas del 11 sin volver a ajustar el modelo original."""
    from tfm.data import read_result

    stored = {name: read_result(root, name) for name in
              ("logistic_predictions", "logistic_monthly", "logistic_metrics")}
    report = stored["logistic_metrics"][1]
    current_versions = {name: version(name) for name in ("scikit-learn", "numpy", "pandas")}
    if (report.get("variant") != VARIANT or report.get("model_parameters") != MODEL_PARAMETERS
            or report.get("model_columns") != MODEL_COLUMNS or report.get("target") != "label"
            or report.get("parameters") != label_report["parameters"]
            or report.get("versions") != current_versions or report.get("experiment_status") != "completed"
            or not report.get("attempt")
            or any(info.get("attempt") != report["attempt"] for _, info in stored.values())):
        raise ValueError("Ejecuta el notebook 11 con las entradas y el entorno actuales antes de las sombras.")
    predictions = stored["logistic_predictions"][0]
    keys = ["split_id", "strategy", "target_period", "label"]
    expected = splits.loc[splits.role.eq("validation"), ["split_id", "target_period"]].merge(
        samples.loc[samples.sample_usable, ["strategy", "target_period", "label"]], on="target_period")
    coverage = summarize_validation(splits, samples)
    try:
        pd.testing.assert_frame_equal(predictions[keys].sort_values(keys[:3]).reset_index(drop=True),
                                      expected[keys].sort_values(keys[:3]).reset_index(drop=True), check_exact=True)
        monthly, metrics = summarize_predictions(predictions, partitions=coverage[["split_id", "strategy"]])
        pd.testing.assert_frame_equal(monthly, stored["logistic_monthly"][0], check_exact=True)
        pd.testing.assert_frame_equal(metrics, stored["logistic_metrics"][0], check_exact=True)
    except (AssertionError, KeyError) as exc:
        raise ValueError("Las salidas del 11 no coinciden con los ejemplos actuales; vuelve a ejecutarlo.") from exc
    return metrics, report


def run_model_shadows(root: Path, *, progress=None) -> tuple[dict, dict]:
    """Ejecutar toda la lista prevista; registrar referencias, no candidatos nuevos."""
    samples, splits, label_report, preparation = load_logistic_inputs(root)
    original_metrics, original_report = _load_original(root, samples, splits, label_report)
    calendar = model_calendar(samples)
    shifts = circular_shifts(len(calendar))
    baseline = _main_metrics(original_metrics).loc[lambda t: t.model.eq("naive")].set_index("strategy")
    attempt = datetime.now(timezone.utc).isoformat()
    record = {"attempt": attempt, "purpose": "circular_shadow_reference", "reference_variant": VARIANT,
              "original_attempt": original_report["attempt"], "model_parameters": MODEL_PARAMETERS,
              "model_columns": MODEL_COLUMNS, "parameters": label_report["parameters"],
              "development": ["1927-01", "1989-12"], "common_months": len(calendar),
              "shift_months": shifts, "minimum_circular_distance": MIN_SHIFT,
              "expected_fits": len(shifts) * 30, "candidate_configurations_added": 0,
              "primary_statistic": "naive_log_loss_minus_model_log_loss",
              "shadow_quantile": SHADOW_QUANTILE, "quantile_method": QUANTILE_METHOD,
              "versions": original_report["versions"]}
    log_path = root / "outputs/experiments/logistic_shadow_trials.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(event):
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False) + "\n")

    records, current_shift = [], None
    append({"status": "started"})
    try:
        if progress:
            progress(0, len(shifts))
        for number, current_shift in enumerate(shifts, 1):
            tables, fit_report = evaluate_logistic(circular_shadow(samples, current_shift), splits)
            main = _main_metrics(tables["logistic_metrics"])
            naive = main.loc[main.model.eq("naive")].set_index("strategy")
            pd.testing.assert_frame_equal(naive[baseline.columns], baseline, check_exact=True)
            for rule in RULES:
                score = main.loc[main.strategy.eq(rule) & main.model.eq("logistic")].iloc[0]
                diagnostics = [d for d in fit_report["diagnostics"] if d["strategy"] == rule]
                complete = (score.status == "completed" and len(diagnostics) == 15
                            and all(d["status"] == "completed" for d in diagnostics)
                            and np.isfinite([score.log_loss, score.auc]).all())
                records.append({"shift_months": current_shift,
                                "circular_distance_months": min(current_shift, len(calendar) - current_shift),
                                "strategy": rule, "examples": int(score.examples),
                                "log_loss": float(score.log_loss), "auc": float(score.auc),
                                "naive_log_loss": float(baseline.loc[rule, "log_loss"]),
                                "log_loss_improvement": float(baseline.loc[rule, "log_loss"] - score.log_loss),
                                "completed_fits": sum(d["status"] == "completed" for d in diagnostics),
                                "status": "completed" if complete else "unavailable"})
            del tables
            if progress and (number % 25 == 0 or number == len(shifts)):
                progress(number, len(shifts))
        shadows = pd.DataFrame(records)
        comparison, summary = compare_shadows(shadows, original_metrics, shifts)
        status = "completed" if summary["shadow_comparison_available"] else "incomplete"
        append({"status": status, **summary, "comparison": json.loads(comparison.to_json(orient="records"))})
    except (Exception, KeyboardInterrupt) as exc:
        append({"status": "failed", "shift_months_at_failure": current_shift,
                "completed_shadow_rows": len(records), "error": str(exc)})
        raise
    report = {**record, **summary, "scope": "development_logistic_shadow_reference_only",
              "experiment_status": status, "common_start": calendar.target_period.iloc[0],
              "common_end": calendar.target_period.iloc[-1], "sample_counts": preparation["sample_counts"],
              "aggregation": original_report["aggregation"], "auc_reference": AUC_REFERENCE,
              "auc_shadow_role": "descriptive_only", "trial_log": "outputs/experiments/logistic_shadow_trials.jsonl",
              "protocol": "docs/sombras_logistica.md",
              "warnings": ["Criterion specified after observing the first model and before computing its shadows.",
                           "Circular references are artificial and dependent; their quantiles are not exact p-values.",
                           "Only transformed features move; labels, signals and CPCV dates stay fixed.",
                           "The operational criterion does not establish economic utility or choose a winning model.",
                           "No post-1989 evaluation, feature selection, SHAP, DSR or PBO is performed."]}
    return {RESULT_NAMES[0]: shadows, RESULT_NAMES[1]: comparison}, report
