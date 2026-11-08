"""Particiones CPCV de descubrimiento: calendario fijo y ejemplos por regla.

Guía 1.B y docs/plan_validacion_temporal.md. Dos bloques de validación,
purga conservadora de un mes y embargo de seis, sin modelos ni selección.
"""

from itertools import combinations

import numpy as np
import pandas as pd

from tfm.diagnostics import START, END
from tfm.features import FEATURE_COLUMNS
from tfm.screening import MIN_HISTORY, RULES, transform_features
from tfm.sources.shiller import INSTRUMENT


N_BLOCKS = 6
VALIDATION_BLOCKS = 2
PURGE_MONTHS = 1
EMBARGO_MONTHS = 6
MODEL_COLUMNS = [f"z_{name}" for name in FEATURE_COLUMNS]
RESULT_NAMES = ("validation_splits", "validation_summary")


def build_temporal_splits() -> tuple[pd.DataFrame, dict]:
    """Particionar fechas completas antes de filtrar por señales o calentamiento.

    Prioridad: validation > purge > embargo > train. El primer mes de embargo
    coincide con la purga posterior; no son siete meses de exclusión posterior.
    """
    months = pd.period_range(START, END, freq="M")
    size = len(months) // N_BLOCKS
    blocks = [months[i*size:(i+1)*size] for i in range(N_BLOCKS)]
    frames, descriptions = [], []
    for split_id, pair in enumerate(combinations(range(N_BLOCKS), VALIDATION_BLOCKS), 1):
        intervals = []
        for index in pair:
            start, end = blocks[index][0], blocks[index][-1]
            if intervals and intervals[-1][1] + 1 == start:
                intervals[-1] = (intervals[-1][0], end)
            else:
                intervals.append((start, end))
        validation = np.zeros(len(months), dtype=bool)
        purge = validation.copy()
        embargo = validation.copy()
        for start, end in intervals:
            validation |= (months >= start) & (months <= end)
            purge |= ((months >= start - PURGE_MONTHS) & (months < start)
                      | (months > end) & (months <= end + PURGE_MONTHS))
            embargo |= (months > end) & (months <= end + EMBARGO_MONTHS)
        roles = np.full(len(months), "train", dtype=object)
        roles[embargo] = "embargo"
        roles[purge] = "purge"
        roles[validation] = "validation"
        frames.append(pd.DataFrame({
            "split_id": split_id, "validation_block_1": pair[0] + 1,
            "validation_block_2": pair[1] + 1, "target_period": months.astype(str),
            "block_id": np.repeat(np.arange(1, N_BLOCKS + 1), size), "role": roles,
            "in_purge_window": purge & ~validation, "in_embargo_window": embargo & ~validation,
        }))
        descriptions.append({"split_id": split_id, "validation_blocks": [i + 1 for i in pair],
                             "validation_intervals": [{"start": str(a), "end": str(b)} for a, b in intervals]})
    report = {
        "development_start": START, "development_end": END, "calendar_months": len(months),
        "n_blocks": N_BLOCKS, "months_per_block": size, "validation_blocks_per_split": VALIDATION_BLOCKS,
        "n_splits": len(frames), "validation_occurrences_per_month": 5,
        "purge_months": PURGE_MONTHS, "embargo_months": EMBARGO_MONTHS,
        "role_priority": ["validation", "purge", "embargo", "train"],
        "embargo_origin": "last validation target month; overlaps posterior purge",
        "blocks": [{"block_id": i + 1, "first_target": str(block[0]), "last_target": str(block[-1]),
                    "months": len(block)} for i, block in enumerate(blocks)],
        "partitions": descriptions,
    }
    return pd.concat(frames, ignore_index=True), report


def prepare_validation_samples(features: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Conservar el calendario por regla; separar pertenencia temporal de cobertura.

    No leer resultados del cribado. La preparación causal fija usa covariables
    pasadas, no las etiquetas ni la asignación de bloques de validación.
    """
    transformed, preparation = transform_features(features)
    required = {"asset", "strategy", "target_period", "decision_period", "label_end_period", "label",
                "label_no_transaction_cost", "has_signal", "features_ready", "training_ready", *FEATURE_COLUMNS}
    months = pd.period_range(START, END, freq="M")
    if (not required <= set(labels) or len(labels) != 2 * len(months)
            or set(labels.strategy) != set(RULES) or not labels.asset.eq(INSTRUMENT).all()
            or not labels.label_end_period.equals(labels.target_period)):
        raise ValueError("Se requieren etiquetas de horizonte mensual dentro de 1927–1989; ejecuta el notebook 08.")
    for name in ("has_signal", "features_ready", "training_ready"):
        if not pd.api.types.is_bool_dtype(labels[name]) or labels[name].isna().any():
            raise ValueError("Marcas de disponibilidad inválidas; ejecuta el notebook 08.")
    if not labels.training_ready.equals(labels.features_ready & labels.has_signal):
        raise ValueError("La muestra de etiquetas no corresponde a sus señales; ejecuta el notebook 08.")
    for name in ("label", "label_no_transaction_cost"):
        if (not pd.api.types.is_numeric_dtype(labels[name]) or pd.api.types.is_bool_dtype(labels[name])
                or not labels[name].isna().equals(~labels.has_signal)
                or not labels.loc[labels.has_signal, name].isin([0, 1]).all()):
            raise ValueError("Una señal activa necesita etiqueta binaria y efectivo etiqueta ausente; ejecuta el notebook 08.")
    for rule in RULES:
        rows = labels.loc[labels.strategy.eq(rule)]
        if (rows.target_period.tolist() != months.astype(str).tolist()
                or rows.decision_period.tolist() != (months - 1).astype(str).tolist()):
            raise ValueError("Fechas de etiquetas ausentes, duplicadas o desalineadas; ejecuta el notebook 08.")
        try:
            pd.testing.assert_frame_equal(rows[FEATURE_COLUMNS].reset_index(drop=True),
                                          features[FEATURE_COLUMNS].reset_index(drop=True), check_exact=True)
            pd.testing.assert_series_equal(rows.features_ready.reset_index(drop=True),
                                           features[FEATURE_COLUMNS].notna().all(axis=1).reset_index(drop=True), check_names=False)
        except AssertionError as exc:
            raise ValueError("Características y etiquetas no coinciden; ejecuta 07 → 08.") from exc
    transformed = transformed.rename(columns={"screening_ready": "causal_features_ready"})
    keep = ["asset", "target_period", "decision_period", "price_source_period", "context_source_period",
            "causal_features_ready", "exclusion_reason", *MODEL_COLUMNS]
    samples = labels[["asset", "strategy", "target_period", "decision_period", "label_end_period",
                      "has_signal", "label", "label_no_transaction_cost"]].merge(
        transformed[keep], on=["asset", "target_period", "decision_period"], how="left", validate="many_to_one")
    samples["sample_usable"] = samples.causal_features_ready & samples.has_signal
    usable_months = transformed.loc[transformed.causal_features_ready, "target_period"]
    report = {"feature_columns": FEATURE_COLUMNS, "model_columns": MODEL_COLUMNS, "min_history": MIN_HISTORY,
              "causal_common_months": len(usable_months),
              "first_causal_target": usable_months.iloc[0] if len(usable_months) else None,
              "last_causal_target": usable_months.iloc[-1] if len(usable_months) else None,
              "excluded_targets": preparation["excluded_targets"],
              "target": "label", "sensitivity_target": "label_no_transaction_cost",
              "sample_counts": [{"strategy": rule, "calendar_months": len(part),
                                 "causal_feature_months": int(part.causal_features_ready.sum()),
                                 "signal_months": int(part.has_signal.sum()),
                                 "usable_examples": int(part.sample_usable.sum()),
                                 "positive": int(part.loc[part.sample_usable, "label"].eq(1).sum()),
                                 "negative": int(part.loc[part.sample_usable, "label"].eq(0).sum())}
                                for rule, part in samples.groupby("strategy", sort=False)]}
    return samples, report


def summarize_validation(splits: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    """Treinta resúmenes; no retirar particiones por su distribución de clases."""
    expected, _ = build_temporal_splits()
    try:
        pd.testing.assert_frame_equal(splits, expected, check_exact=True)
    except AssertionError as exc:
        raise ValueError("Las particiones no corresponden al calendario y exclusiones fijados.") from exc
    months = pd.period_range(START, END, freq="M").astype(str).tolist()
    if (len(samples) != 2 * len(months) or set(samples.strategy) != set(RULES)
            or any(samples.loc[samples.strategy.eq(rule), "target_period"].tolist() != months for rule in RULES)):
        raise ValueError("Se requiere el calendario completo preparado para ambas reglas.")
    merged = splits.merge(samples, on="target_period", how="left", validate="many_to_many")
    rows = []
    for (split_id, rule), part in merged.groupby(["split_id", "strategy"], sort=True):
        counts = {"split_id": int(split_id), "strategy": rule,
                  "validation_block_1": int(part.validation_block_1.iloc[0]),
                  "validation_block_2": int(part.validation_block_2.iloc[0]),
                  "purge_calendar_months": int(part.role.eq("purge").sum()),
                  "embargo_calendar_months": int(part.role.eq("embargo").sum()),
                  "embargo_window_months": int(part.in_embargo_window.sum()),
                  "purged_usable_examples": int((part.role.eq("purge") & part.sample_usable).sum()),
                  "embargoed_usable_examples": int((part.role.eq("embargo") & part.sample_usable).sum())}
        for role in ("train", "validation"):
            subset = part.loc[part.role.eq(role)]
            usable = subset.loc[subset.sample_usable]
            counts.update({f"{role}_calendar_months": len(subset),
                           f"{role}_feature_months": int(subset.causal_features_ready.sum()),
                           f"{role}_signal_months": int(subset.has_signal.sum()),
                           f"{role}_examples": len(usable),
                           f"{role}_positive": int(usable.label.eq(1).sum()),
                           f"{role}_negative": int(usable.label.eq(0).sum())})
        counts["train_classifier_ready"] = counts["train_positive"] > 0 and counts["train_negative"] > 0
        counts["validation_auc_estimable"] = counts["validation_positive"] > 0 and counts["validation_negative"] > 0
        rows.append(counts)
    return pd.DataFrame(rows)
