"""Series walk-forward sincronizadas para el análisis de sobreajuste."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.boosting import (KEYS, PROBABILITIES as BOOSTING_PROBABILITIES, VARIANTS as BOOSTING_VARIANTS,
                          load_boosting_reference)
from tfm.clustered_mda import VARIANT as MDA_VARIANT
from tfm.ebm import EBM_PARAMETERS, VARIANT as EBM_VARIANT
from tfm.economic_validation import LINEAR_VARIANTS, TEST_INTERVAL, aligned_accounts
from tfm.economics import (ACCOUNT_LABELS, DECISION_POLICY, MODEL_PROBABILITIES,
                           RESULT_NAMES as ECONOMIC_RESULTS, build_economic_decisions, load_economic_inputs)
from tfm.feature_blocks import BLOCKS, VARIANTS as BLOCK_VARIANTS, fit_feature_block
from tfm.forest import PROBABILITIES as FOREST_PROBABILITIES, VARIANTS as FOREST_VARIANTS
from tfm.forest_economics import ACCOUNT as FOREST_ACCOUNT, RESULT_NAMES as FOREST_ECONOMIC_RESULTS
from tfm.logistic import VARIANT as ALL_FEATURES_VARIANT
from tfm.screening import RULES
from tfm.simulation import simulate_baselines
from tfm.walk_forward import SIGNAL_COLUMNS, build_walk_forward_splits
from tfm.walk_forward_ablation import REMOVAL_MODELS


RESULT_NAME = "development_selection_returns"
FILTERS = (*[f"L2_{name}" for name in LINEAR_VARIANTS], *REMOVAL_MODELS.values(),
           *BLOCKS, *FOREST_VARIANTS, *BOOSTING_VARIANTS, "EBM_M1")
REFERENCES = ("original", "bear", "volatility", "buy_and_hold", "cash")


def load_selection_inputs(root: Path) -> tuple:
    from tfm.data import read_result

    _, signals, components, linear, parameters, attempts = load_economic_inputs(root)
    saved_accounts, saved_report = read_result(root, ECONOMIC_RESULTS[1])
    if (saved_report.get("experiment_status") != "completed" or saved_report.get("test_interval") != TEST_INTERVAL
            or saved_report.get("source_attempts") != attempts or saved_report.get("parameters") != parameters
            or saved_report.get("decision_policy") != DECISION_POLICY or not saved_report.get("attempt")):
        raise ValueError("Ejecuta las secciones 19–22 del notebook 14 con las predicciones actuales.")
    aligned_accounts(saved_accounts, set(ACCOUNT_LABELS))

    samples, boosted, lineage = load_boosting_reference(root)
    candidates = {}
    forecasts = linear[KEYS].set_index(KEYS)

    def add_candidate(name, frame, probability, variant, source, attempt):
        values = frame.set_index(KEYS, verify_integrity=True)[probability]
        if name in candidates or len(values) != len(forecasts) or not forecasts.index.isin(values.index).all():
            raise ValueError(f"Las probabilidades de {name} no coinciden con la muestra común de M1.")
        if not attempt:
            raise ValueError(f"Falta el intento de origen de {name}.")
        forecasts[name] = values
        candidates[name] = {"variant": variant, "source": source, "attempt": attempt}

    def read_forecasts(name, links):
        frame, report = read_result(root, name)
        if (report.get("experiment_status") != "completed" or report.get("test_interval") != TEST_INTERVAL
                or report.get("parameters") != parameters or not report.get("attempt")
                or any(report.get(key) != value for key, value in links.items())):
            raise ValueError(f"Repite la sección que guarda {name} con las referencias actuales.")
        return frame, report

    for name, variant in LINEAR_VARIANTS.items():
        source = {"M1": "walk_forward_predictions", "M2": "walk_forward_regime_predictions",
                  "M3": "walk_forward_interaction_predictions"}[name]
        add_candidate(f"L2_{name}", linear, MODEL_PROBABILITIES[name], variant, source,
                      attempts["M0_M1" if name == "M1" else name])

    shared = {"reference_attempt": attempts["M2"], "baseline_attempt": attempts["M0_M1"]}
    removal_name = "walk_forward_ablation_predictions"
    removals, removal_report = read_forecasts(removal_name, shared)
    removal_variants = {row["subset_model"]: row for row in removal_report["variants"]}
    for name in REMOVAL_MODELS.values():
        info = removal_variants[name]
        add_candidate(name, removals.loc[removals.subset_model.eq(name)], "probability_without",
                      info["variant"], removal_name, info["attempt"])

    forest_name = "forest_walk_forward_predictions"
    forest, forest_report = read_forecasts(forest_name, {**shared, "attempt": lineage["forest_attempt"]})
    for name, variant in FOREST_VARIANTS.items():
        add_candidate(name, forest, FOREST_PROBABILITIES[name], variant, forest_name,
                      forest_report["variant_attempts"][name])

    boosting_name = "boosting_walk_forward_predictions"
    _, boosting_report = read_forecasts(boosting_name, {**shared, "attempt": lineage["boosting_attempt"],
                                                       "forest_attempt": lineage["forest_attempt"]})
    for name, variant in BOOSTING_VARIANTS.items():
        add_candidate(name, boosted, BOOSTING_PROBABILITIES[name], variant, boosting_name,
                      boosting_report["variant_attempts"][name])

    ebm_name = "ebm_walk_forward_predictions"
    ebm, ebm_report = read_forecasts(ebm_name, {**shared, "variant": EBM_VARIANT, "model_parameters": EBM_PARAMETERS,
        "forest_attempt": lineage["forest_attempt"], "boosting_attempt": lineage["boosting_attempt"]})
    add_candidate("EBM_M1", ebm, "probability_ebm", EBM_VARIANT, ebm_name, ebm_report["attempt"])

    forest_account_path = root / "data/processed" / f"{FOREST_ECONOMIC_RESULTS[1]}.parquet"
    if forest_account_path.is_file():
        previous, report = read_result(root, FOREST_ECONOMIC_RESULTS[1])
        if (report.get("source_attempts") != {"forest": lineage["forest_attempt"],
                                               "economic_references": saved_report["attempt"]}
                or report.get("parameters") != parameters or report.get("experiment_status") != "completed"
                or report.get("test_interval") != TEST_INTERVAL or report.get("decision_policy") != DECISION_POLICY):
            raise ValueError("Actualiza la cuenta guardada de RF_M1 de las secciones 40–41.")
        saved_accounts = pd.concat([saved_accounts, previous.loc[previous.strategy.eq(FOREST_ACCOUNT)]],
                                   ignore_index=True)

    columns = list(SIGNAL_COLUMNS)
    splits = build_walk_forward_splits()
    for name, added in BLOCKS.items():
        columns.extend(added)
        fitted = fit_feature_block(samples, splits, linear, columns)
        add_candidate(name, fitted, "probability_logistic", BLOCK_VARIANTS[name],
                      "reproducción del recorrido por bloques", attempts["M0_M1"])
        candidates[name]["model_columns"] = list(columns)
    return signals, components, forecasts.reset_index(), parameters, saved_accounts, candidates, saved_report["attempt"]


def validate_selection_returns(table: pd.DataFrame) -> None:
    """Verificar el rectángulo de cuentas y meses antes de publicar o leer."""
    required = {"rule", "role", "policy", "period", "net_return", "rf_return"}
    if (not required <= set(table) or set(table.rule) != set(RULES)
            or set(table.role) != {"candidate", "reference"}):
        raise ValueError("Se requieren las dos reglas, sus filtros y sus referencias.")
    risk_free = []
    for _, rows in table.groupby("rule"):
        for role, expected in (("candidate", FILTERS), ("reference", REFERENCES)):
            if set(rows.loc[rows.role.eq(role), "policy"]) != set(expected):
                raise ValueError("El conjunto de series no coincide con el definido para DSR y PBO.")
        _, rf = aligned_accounts(rows.rename(columns={"policy": "strategy"}), set(FILTERS) | set(REFERENCES))
        risk_free.append(rf)
    if not np.array_equal(risk_free[0], risk_free[1]) or table.net_return.le(-1).any():
        raise ValueError("Las reglas deben compartir el efectivo y conservar capital positivo.")


def build_selection_returns(signals: pd.DataFrame, components: pd.DataFrame, forecasts: pd.DataFrame,
                            parameters: dict, saved_accounts: pd.DataFrame) -> pd.DataFrame:
    decisions = build_economic_decisions(signals, forecasts, model_probabilities={name: name for name in FILTERS})
    fields = ["period", "net_return", "rf_return"]
    parts = []
    for name in FILTERS:
        filtered = signals.copy()
        for rule in RULES:
            rows = decisions.loc[decisions.model.eq(name) & decisions.rule.eq(rule)]
            filtered[f"{rule}_signal"] = rows.filtered_signal.to_numpy()
        simulated = simulate_baselines(components, filtered, parameters, strategies=RULES)
        for rule in RULES:
            rows = simulated.loc[simulated.strategy.eq(rule), fields]
            account = f"{rule}_{name.removeprefix('L2_').lower()}"
            previous = saved_accounts.loc[saved_accounts.strategy.eq(account), fields]
            if name.startswith("L2_") or not previous.empty:
                try:
                    pd.testing.assert_frame_equal(rows.reset_index(drop=True), previous.reset_index(drop=True),
                                                  check_exact=True)
                except AssertionError as exc:
                    raise ValueError(f"La cuenta de {rule} con {name} no reproduce los retornos publicados.") from exc
            parts.append(rows.assign(rule=rule, policy=name, role="candidate"))

    for rule in RULES:
        names = (rule, f"{rule}_bear", f"{rule}_volatility", "buy_and_hold", "cash")
        for policy, account in zip(REFERENCES, names, strict=True):
            rows = saved_accounts.loc[saved_accounts.strategy.eq(account), fields]
            parts.append(rows.assign(rule=rule, policy=policy, role="reference"))

    matrix = pd.concat(parts, ignore_index=True)[["rule", "role", "policy", *fields]]
    validate_selection_returns(matrix)
    return matrix


def run_selection_returns(root: Path) -> tuple[pd.DataFrame, dict]:
    *inputs, candidates, reference_attempt = load_selection_inputs(root)
    if set(candidates) != set(FILTERS):
        raise ValueError("Faltan variantes del conjunto económico fijado.")
    matrix = build_selection_returns(*inputs)
    return matrix, {"attempt": datetime.now(timezone.utc).isoformat(), "test_interval": TEST_INTERVAL,
        "parameters": inputs[3], "decision_policy": DECISION_POLICY, "candidates": candidates,
        "references": list(REFERENCES), "economic_reference_attempt": reference_attempt,
        "aliases": {ALL_FEATURES_VARIANT: BLOCK_VARIANTS["Con_regimen"]},
        "excluded": {MDA_VARIANT: "selección interna CPCV, sin equivalente cronológico ya definido",
                     "M0": "referencia de frecuencia con cuentas duplicadas de la regla original o el efectivo"},
        "protocol": "docs/series_dsr_pbo.md"}
