"""Primer experimento L2: probabilidades de meta-etiquetas en CPCV.

Diseño: docs/primer_modelo.md. No selecciona variables, umbrales o modelos.
La media de cinco predicciones es un resumen de descubrimiento, no una cartera.
"""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from tfm.validation import MODEL_COLUMNS, prepare_validation_samples, summarize_validation


RESULT_NAMES = ("logistic_predictions", "logistic_monthly", "logistic_metrics", "logistic_coefficients")
MODEL_PARAMETERS = {"C": 1.0, "l1_ratio": 0.0, "solver": "lbfgs", "fit_intercept": True,
                    "class_weight": None, "max_iter": 2000, "tol": 1e-8}
VARIANT = "logistic_l2_C1_all10_central"
EXPECTED_PREDICTIONS = 5


def _sklearn():
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.metrics import log_loss, roc_auc_score
    except ImportError as exc:
        raise ValueError('Falta scikit-learn. Instala el extra con python -m pip install -e ".[models]".') from exc
    return LogisticRegression, ConvergenceWarning, log_loss, roc_auc_score


def fit_partition(train: pd.DataFrame, validation: pd.DataFrame, *, strategy: str,
                  split_id: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Ajustar únicamente con train; los resultados de validación solo se conservan."""
    LogisticRegression, ConvergenceWarning, _, _ = _sklearn()
    for rows in (train, validation):
        if (not rows.label.isin([0, 1]).all()
                or not np.isfinite(rows[MODEL_COLUMNS].to_numpy(dtype=float)).all()):
            raise ValueError("Se necesitan ejemplos completos y etiquetas binarias.")
    if set(train.target_period) & set(validation.target_period):
        raise ValueError("Entrenamiento y validación deben tener meses distintos.")
    predictions = validation[["target_period", "label"]].reset_index(drop=True).copy()
    predictions.insert(0, "strategy", strategy)
    predictions.insert(0, "split_id", split_id)
    predictions["probability_naive"] = float(train.label.mean()) if len(train) else np.nan
    predictions["probability_logistic"] = np.nan
    terms = ["intercept", *MODEL_COLUMNS]
    coefficients = pd.DataFrame({"split_id": split_id, "strategy": strategy,
                                 "term": terms, "coefficient": np.nan})
    diagnostic = {"split_id": split_id, "strategy": strategy, "train_examples": len(train),
                  "validation_examples": len(validation), "train_positive": int(train.label.eq(1).sum()),
                  "iterations": None, "status": "train_single_class"}
    if train.label.nunique() == 2:
        model = LogisticRegression(**MODEL_PARAMETERS)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            try:
                model.fit(train[MODEL_COLUMNS].to_numpy(dtype=float), train.label.to_numpy(dtype=int))
            except ConvergenceWarning as exc:
                raise RuntimeError(f"La logística no converge en {strategy}, partición {split_id}; no se han cambiado parámetros.") from exc
        if len(validation):
            positive = int(np.flatnonzero(model.classes_ == 1)[0])
            predictions["probability_logistic"] = model.predict_proba(
                validation[MODEL_COLUMNS].to_numpy(dtype=float))[:, positive]
        coefficients["coefficient"] = np.r_[model.intercept_, model.coef_[0]]
        diagnostic.update(status="completed", iterations=int(model.n_iter_[0]))
    elif train.empty:
        diagnostic["status"] = "empty_training"
    predictions["fit_status"] = diagnostic["status"]
    coefficients["fit_status"] = diagnostic["status"]
    return predictions, coefficients, diagnostic


def summarize_predictions(predictions: pd.DataFrame, *,
                          partitions: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Una media por mes, conservando las particiones indicadas aunque estén vacías."""
    _, _, log_loss, roc_auc_score = _sklearn()
    key = ["split_id", "strategy", "target_period"]
    if predictions.empty or predictions.duplicated(key).any() or not predictions.label.isin([0, 1]).all():
        raise ValueError("Predicciones vacías, duplicadas o sin etiqueta binaria.")
    for name in ("probability_logistic", "probability_naive"):
        values = predictions[name].dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError("Las probabilidades deben ser finitas y estar entre cero y uno.")
    by_month = predictions.groupby(["strategy", "target_period"], sort=True)
    if not by_month.size().eq(EXPECTED_PREDICTIONS).all() or not by_month.label.nunique().eq(1).all():
        raise ValueError("Cada ejemplo necesita cinco predicciones con la misma etiqueta.")
    monthly = by_month.agg(label=("label", "first"), validation_appearances=("split_id", "size"),
                           available_logistic=("probability_logistic", "count"),
                           available_naive=("probability_naive", "count"),
                           probability_logistic=("probability_logistic", "mean"),
                           probability_naive=("probability_naive", "mean")).reset_index()
    for model in ("logistic", "naive"):
        monthly.loc[monthly[f"available_{model}"].ne(EXPECTED_PREDICTIONS), f"probability_{model}"] = np.nan
    records = []
    observed = {(int(split), rule): rows
                for (split, rule), rows in predictions.groupby(["split_id", "strategy"], sort=True)}
    keys = list(observed) if partitions is None else list(
        partitions[["split_id", "strategy"]].itertuples(index=False, name=None))
    if len(set(keys)) != len(keys) or not set(observed) <= set(keys):
        raise ValueError("Las particiones deben ser únicas e incluir todas las predicciones.")
    empty = predictions.iloc[:0]
    groups = [("partition", int(split), rule, observed.get((int(split), rule), empty))
              for split, rule in keys]
    groups += [("monthly_mean", None, rule, rows) for rule, rows in monthly.groupby("strategy", sort=True)]
    for aggregation, split, rule, rows in groups:
        for model in ("logistic", "naive"):
            y = rows.label.to_numpy(dtype=int)
            p = rows[f"probability_{model}"].to_numpy(dtype=float)
            complete = bool(len(y) and np.isfinite(p).all())
            records.append({"aggregation": aggregation, "split_id": split, "strategy": rule, "model": model,
                            "examples": len(y), "positive": int(y.sum()), "negative": int(len(y) - y.sum()),
                            "status": ("empty_validation" if not len(y) else
                                       "completed" if complete else "unavailable_predictions"),
                            "log_loss": float(log_loss(y, p, labels=[0, 1])) if complete else None,
                            "auc": float(roc_auc_score(y, p)) if complete and len(np.unique(y)) == 2 else None})
    metrics = pd.DataFrame(records)
    metrics["split_id"] = metrics.split_id.astype("Int64")
    return monthly, metrics


def evaluate_logistic(samples: pd.DataFrame, splits: pd.DataFrame) -> tuple[dict, dict]:
    """Treinta ajustes fijos: quince particiones para cada una de las dos reglas."""
    coverage = summarize_validation(splits, samples)  # Comprueba el calendario fijado.
    usable = samples.loc[samples.sample_usable].copy()
    predictions, coefficients, diagnostics = [], [], []
    for item in coverage.itertuples(index=False):
        calendar = splits.loc[splits.split_id.eq(item.split_id), ["target_period", "role"]]
        rows = usable.loc[usable.strategy.eq(item.strategy)].merge(calendar, on="target_period", validate="one_to_one")
        p, c, d = fit_partition(rows.loc[rows.role.eq("train")], rows.loc[rows.role.eq("validation")],
                                strategy=item.strategy, split_id=int(item.split_id))
        predictions.append(p)
        coefficients.append(c)
        diagnostics.append(d)
    predictions = pd.concat(predictions, ignore_index=True)
    monthly, metrics = summarize_predictions(predictions, partitions=coverage[["split_id", "strategy"]])
    if len(monthly) != len(usable):
        raise ValueError("La evaluación no conserva todos los ejemplos utilizables.")
    tables = dict(zip(RESULT_NAMES, [predictions, monthly, metrics, pd.concat(coefficients, ignore_index=True)]))
    report = {"scope": "development_logistic_probabilities_only", "variant": VARIANT,
              "model_parameters": MODEL_PARAMETERS, "model_columns": MODEL_COLUMNS, "target": "label",
              "development_start": "1927-01", "development_end": "1989-12", "partitions": 15,
              "aggregation": "arithmetic mean of five validation probabilities per rule and target month",
              "validation_predictions_per_example": EXPECTED_PREDICTIONS, "diagnostics": diagnostics,
              "metric_probability_clipping": "scikit-learn float64 machine epsilon; raw probabilities preserved",
              "skill_auc_reference": 0.54, "skill_gate_status": "pending_model_shadows",
              "versions": {name: version(name) for name in ("scikit-learn", "numpy", "pandas")},
              "warnings": ["CPCV discovery can train on future blocks; this is not a real-time strategy.",
                           "Monthly probability averages are not CPCV return paths or independent repetitions.",
                           "No feature selection, probability calibration, threshold tuning or economic evaluation.",
                           "Model shadows, Clustered MDA, SHAP, DSR and PBO remain pending.",
                           "Shiller monthly means and reconstructed dividends retain their availability limitations."]}
    return tables, report


def run_logistic_experiment(root: Path) -> tuple[dict, dict]:
    """Leer entradas verificadas y registrar cada intento antes del primer ajuste.

    El historial científico se conserva aparte de las tablas reemplazables. Una
    repetición es otro intento de la misma variante, no quince modelos candidatos.
    """
    from tfm.data import read_result

    _sklearn()
    features, _ = read_result(root, "monthly_features")
    labels, label_report = read_result(root, "labelled_signals")
    samples, preparation = prepare_validation_samples(features, labels)
    splits, _ = read_result(root, "validation_splits")
    saved_summary, _ = read_result(root, "validation_summary")
    try:
        pd.testing.assert_frame_equal(saved_summary, summarize_validation(splits, samples), check_exact=True)
    except AssertionError as exc:
        raise ValueError("Las particiones no corresponden a las entradas actuales; ejecuta el notebook 10.") from exc
    path = root / "outputs/experiments/logistic_trials.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    attempt = datetime.now(timezone.utc).isoformat()
    record = {"attempt": attempt, "variant": VARIANT, "strategies": ["momentum", "reversal"],
              "model_parameters": MODEL_PARAMETERS, "model_columns": MODEL_COLUMNS, "target": "label",
              "parameters": label_report["parameters"], "development": ["1927-01", "1989-12"],
              "partitions": 15, "candidate_configurations_per_rule": 1,
              "aggregation": "mean_of_five_validation_probabilities",
              "scikit_learn_version": version("scikit-learn")}

    def append(event):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, **event}, ensure_ascii=False, allow_nan=False) + "\n")

    append({"status": "started"})
    try:
        tables, report = evaluate_logistic(samples, splits)
        main = tables["logistic_metrics"].loc[lambda t: t.aggregation.eq("monthly_mean")]
        results = json.loads(main.to_json(orient="records"))
        status = "completed" if main.status.eq("completed").all() else "incomplete"
        append({"status": status, "metrics": results})
    except (Exception, KeyboardInterrupt) as exc:
        append({"status": "failed", "error": str(exc)})
        raise
    report.update(parameters=label_report["parameters"], sample_counts=preparation["sample_counts"],
                  attempt=attempt, experiment_status=status,
                  trial_log="outputs/experiments/logistic_trials.jsonl", protocol="docs/primer_modelo.md")
    return tables, report
