"""Cribado supervisado y compuestos de régimen ajustados por partición."""

from pathlib import Path

import numpy as np
import pandas as pd

from tfm.diagnostics import END
from tfm.features import REGIME_FAMILIES as FAMILIES
from tfm.screening import (REGIME_FEATURE_COLUMNS, REGIME_MIN_HISTORY, RESULT_NAMES as SCREENING_RESULTS,
                           RULES, screen_training_relationships)
from tfm.validation import MODEL_COLUMNS, REGIME_CPCV_START, REGIME_RESULT_NAMES
from tfm.walk_forward import FIRST_TEST_YEAR, LAST_TEST_YEAR, build_walk_forward_splits


RESULT_NAMES = ("regime_120_screening", "regime_120_members", "regime_120_compounds")


def fit_compound_members(training: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Elegir miembros por regla con BH direccional y coherencia en el entrenamiento."""
    tests = screen_training_relationships(training)
    eligible = set(tests.loc[tests.passes_directional_screen, ["strategy", "feature"]].itertuples(index=False, name=None))
    columns = {f"z_{feature}": feature for feature in REGIME_FEATURE_COLUMNS}
    prices = training.loc[training.strategy.eq(RULES[0]) & training.screening_ready, list(columns)]
    correlation = prices.rename(columns=columns).corr(method="spearman")
    records = []
    for rule in RULES:
        for family, candidates in FAMILIES.items():
            members = []
            for priority, feature in enumerate(candidates, start=1):
                passes = (rule, feature) in eligible
                minimum = np.nan
                if not passes:
                    status = "screen_excluded"
                elif not members:
                    status = "selected"
                else:
                    pairs = correlation.loc[feature, members].to_numpy(dtype=float)
                    if np.isfinite(pairs).all():
                        minimum = float(pairs.min())
                        status = "selected" if minimum > 0 else "nonpositive_correlation"
                    else:
                        status = "unavailable_correlation"
                if status == "selected":
                    members.append(feature)
                records.append({"strategy": rule, "family": family, "feature": feature, "priority": priority,
                                "passes_screen": passes, "selected": status == "selected",
                                "minimum_spearman": minimum, "status": status})
    return tests, pd.DataFrame(records)


def apply_compounds(predictors: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """Aplicar los miembros ya fijados para una regla, con igual peso y sin reestimar nada."""
    selected = members.loc[members.selected]
    values = {family: predictors[[f"z_{feature}" for feature in rows.feature]].mean(axis=1, skipna=False)
              for family, rows in selected.groupby("family", sort=False)}
    return pd.DataFrame(values, index=predictors.index).reindex(columns=list(FAMILIES))


def run_regime_compounds(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    """Formar los compuestos con el entrenamiento exterior de cada recorrido."""
    from tfm.data import read_result

    monthly, screening = read_result(root, SCREENING_RESULTS[0])
    cpcv, _ = read_result(root, REGIME_RESULT_NAMES[0])
    if (screening.get("status") != "passed" or screening.get("min_history") != REGIME_MIN_HISTORY
            or screening.get("first_target") != REGIME_CPCV_START or screening.get("last_target") != END):
        raise ValueError("Ejecuta el notebook 09 para preparar las series mensuales con 120 meses.")
    ready = monthly.loc[monthly.screening_ready]
    expected = pd.period_range(REGIME_CPCV_START, END, freq="M").astype(str).tolist()
    if (set(ready.strategy) != set(RULES)
            or any(ready.loc[ready.strategy.eq(rule), "target_period"].tolist() != expected for rule in RULES)
            or not np.isfinite(ready[MODEL_COLUMNS].to_numpy(dtype=float)).all()):
        raise ValueError("Las características mensuales no cubren el calendario común; revisa el notebook 09.")

    tests, members, compounds = [], [], []
    for scheme, splits in (("walk_forward", build_walk_forward_splits()), ("CPCV", cpcv)):
        for split_id, calendar in splits.groupby("split_id", sort=True):
            training = ready.loc[ready.target_period.isin(calendar.loc[calendar.role.eq("train"), "target_period"])]
            fold_tests, fold_members = fit_compound_members(training)
            tests.append(fold_tests.assign(validation_scheme=scheme, split_id=split_id))
            members.append(fold_members.assign(validation_scheme=scheme, split_id=split_id))
            dates = calendar.loc[calendar.role.isin(["train", "validation"]), ["target_period", "role"]]
            # Los retornos solo se han usado arriba. Aquí se aplican las medias fijas a los predictores.
            rows = ready[["strategy", "target_period", *MODEL_COLUMNS]].merge(dates, on="target_period",
                                                                                validate="many_to_one")
            for rule, predictors in rows.groupby("strategy", sort=False):
                values = apply_compounds(predictors, fold_members.loc[fold_members.strategy.eq(rule)])
                compounds.append(predictors[["strategy", "target_period", "role"]].join(values)
                                 .assign(validation_scheme=scheme, split_id=split_id))

    tables = {name: pd.concat(parts, ignore_index=True) for name, parts in zip(
        RESULT_NAMES, (tests, members, compounds), strict=True)}
    report = {"scope": "development_compounds_by_outer_training", "min_history": REGIME_MIN_HISTORY,
              "common_period": [REGIME_CPCV_START, END],
              "walk_forward_test_years": [FIRST_TEST_YEAR, LAST_TEST_YEAR],
              "families": {family: list(candidates) for family, candidates in FAMILIES.items()},
              "parameters": screening["parameters"], "selection": "directional BH then positive Spearman",
              "protocol": "docs/hipotesis_y_cribado.md#cribado-y-compuestos-en-cada-entrenamiento"}
    return tables, report
