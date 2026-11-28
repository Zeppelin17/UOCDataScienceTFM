"""Comparación emparejada, reutilización de M1 y guardado de M2."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.data import read_result, save_result
from tfm.features import FEATURE_COLUMNS, REGIME_FAMILIES
from tfm.regime_compounds import RESULT_NAMES as COMPOUND_RESULTS
from tfm.regime_m2 import RESULT_NAMES, fit_m2_partitions
from tfm.regime_reference import run_regime_reference
from tfm.screening import REGIME_MIN_HISTORY
from tfm.validation import (REGIME_CPCV_START, REGIME_RESULT_NAMES, build_temporal_splits,
                            prepare_validation_samples, summarize_validation)
from tfm.walk_forward import SIGNAL_COLUMNS, build_walk_forward_splits
from test_logistic import PARAMETERS, fixture_samples


def test_m2_fits_with_training_only_and_reuses_reference_without_compounds():
    months = pd.period_range("1950-01", periods=12, freq="M").astype(str)
    years = np.arange(len(months), dtype=float)
    samples = pd.concat([pd.DataFrame({"strategy": rule, "target_period": months, "label": np.arange(12) % 2,
        "sample_usable": True, SIGNAL_COLUMNS[0]: years / 12, SIGNAL_COLUMNS[1]: np.sin(years)})
        for rule in ("momentum", "reversal")], ignore_index=True)
    calendar = pd.DataFrame({"split_id": 1, "target_period": months,
                             "role": ["train"] * 8 + ["validation"] * 4})
    compounds = samples[["strategy", "target_period"]].merge(calendar, on="target_period")
    for name in REGIME_FAMILIES:
        compounds[name] = np.nan
    compounds.loc[compounds.strategy.eq("momentum"), "credit"] = np.cos(years)
    reference = samples.loc[samples.target_period.isin(months[8:]), ["strategy", "target_period", "label"]].copy()
    reference = reference.assign(split_id=1, probability_m1=np.linspace(.2, .8, len(reference)))

    predictions, coefficients, diagnostics = fit_m2_partitions(samples, calendar, compounds, reference)
    fallback = predictions.loc[predictions.strategy.eq("reversal")]
    assert fallback.fit_status_m2.eq("reused_m1").all() and fallback.probability_m2.equals(fallback.probability_m1)
    assert set(coefficients.term) == {"intercept", *SIGNAL_COLUMNS, "credit"}
    assert {row["status"] for row in diagnostics} == {"completed", "reused_m1"}

    changed = samples.copy()
    held = changed.target_period.isin(months[8:])
    changed.loc[held, "label"] = 1 - changed.loc[held, "label"]
    held_reference = reference.assign(label=1 - reference.label)
    repeated, terms, _ = fit_m2_partitions(changed, calendar, compounds, held_reference)
    pd.testing.assert_frame_equal(terms, coefficients, check_exact=True)
    pd.testing.assert_series_equal(repeated.probability_m2, predictions.probability_m2, check_exact=True)
    compounds.loc[compounds.strategy.eq("momentum") & compounds.role.eq("validation"), "credit"] = np.nan
    with pytest.raises(ValueError, match="disponibilidad de los compuestos"):
        fit_m2_partitions(samples, calendar, compounds, reference)


def test_m2_notebook_saves_comparable_results_and_keeps_reference(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    features, labels, _ = fixture_samples()
    samples, prep = prepare_validation_samples(features, labels, min_history=REGIME_MIN_HISTORY)
    cpcv, cal = build_temporal_splits(calendar_start=REGIME_CPCV_START)
    coverage = summarize_validation(cpcv, samples, calendar_start=REGIME_CPCV_START)
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    save_result(tmp_path, REGIME_RESULT_NAMES[0], cpcv, {**cal, **prep})
    save_result(tmp_path, REGIME_RESULT_NAMES[1], coverage, {**cal, **prep})
    tables, info = run_regime_reference(tmp_path)
    for name, table in tables.items():
        save_result(tmp_path, name, table, info)
    compound_info = {"min_history": REGIME_MIN_HISTORY, "parameters": PARAMETERS,
                     "families": {name: list(values) for name, values in REGIME_FAMILIES.items()}}
    pieces = []
    for scheme, calendar in (("walk_forward", build_walk_forward_splits()), ("CPCV", cpcv)):
        dates = calendar.loc[calendar.role.isin(["train", "validation"]), ["split_id", "target_period", "role"]]
        predictors = samples.loc[samples.causal_features_ready, ["strategy", "target_period", "z_credit_spread_pp"]]
        joined = dates.merge(predictors, on="target_period").assign(validation_scheme=scheme)
        for name in REGIME_FAMILIES:
            joined[name] = np.nan
        active = joined.strategy.eq("momentum") & joined.split_id.eq(2)
        joined["credit"] = joined.pop("z_credit_spread_pp").where(active)
        pieces.append(joined)
    compounds = pd.concat(pieces, ignore_index=True)
    save_result(tmp_path, COMPOUND_RESULTS[2], compounds, compound_info)
    existing = {p: p.read_bytes() for p in (tmp_path / "data/processed").glob("*")}

    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("IPython.display.display", lambda *_: None)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    cell, = [c for c in notebook["cells"] if c["cell_type"] == "code" and "regime-m2-120" in c["metadata"].get("tags", [])]
    assert cell["execution_count"] is None and not cell["outputs"]
    state = {}
    exec(compile("".join(cell["source"]), "14:regime-m2-120", "exec"), state)
    assert all(path.read_bytes() == content for path, content in existing.items())
    report = state["informe_m2_120"]
    assert report["experiment_status"] == "completed" and report["reference_attempt"] == info["attempt"]
    for name, result in state["tablas_m2_120"].items():
        saved, saved_report = read_result(tmp_path, name)
        pd.testing.assert_frame_equal(saved, result, check_exact=True)
        assert saved_report["attempt"] == report["attempt"]
    comparisons = state["comparacion_m2_120"]
    assert len(comparisons) == 116 and comparisons.loc[comparisons.strategy.eq("reversal"), "auc_improvement"].eq(0).all()
    events = [json.loads(line) for line in (tmp_path / report["trial_log"]).read_text().splitlines()]
    assert [event["status"] for event in events] == ["started", "completed"]
    save_result(tmp_path, COMPOUND_RESULTS[2], compounds, compound_info)
    assert not any((tmp_path / f"data/processed/{name}.parquet").exists() for name in RESULT_NAMES)
