"""Coherencia de los compuestos, aislamiento de la prueba y recorrido del notebook."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tfm.data import read_result, save_result
from tfm.regime_compounds import RESULT_NAMES, apply_compounds, fit_compound_members, run_regime_compounds
from tfm.screening import RESULT_NAMES as SCREENING_RESULTS, RULES
from tfm.validation import MODEL_COLUMNS, REGIME_CPCV_START, REGIME_RESULT_NAMES, build_temporal_splits


def monthly_sample():
    months = pd.period_range(REGIME_CPCV_START, "1989-12", freq="M").astype(str)
    rng = np.random.default_rng(586)
    trend = rng.normal(size=len(months))
    noise = rng.normal(scale=2, size=len(months))
    features = pd.DataFrame(rng.normal(size=(len(months), len(MODEL_COLUMNS))), columns=MODEL_COLUMNS)
    features["z_market_return_24m"] = trend + noise
    features["z_drawdown_12m"] = trend - noise
    features["z_distance_ma_12m"] = trend + .7 * noise
    return pd.concat([
        features.assign(strategy="momentum", target_period=months, screening_ready=True, anomaly_return=.01 * trend),
        features.assign(strategy="reversal", target_period=months, screening_ready=True,
                        anomaly_return=rng.normal(scale=.01, size=len(months))),
    ], ignore_index=True)


def test_compound_uses_fixed_priority_and_excludes_negative_correlations():
    monthly = monthly_sample()
    tests, members = fit_compound_members(monthly)
    assert len(tests) == 32
    momentum = members.loc[members.strategy.eq("momentum")].set_index("feature")
    assert momentum.loc["market_return_24m", "selected"]
    assert momentum.loc["drawdown_12m", "passes_screen"]
    assert momentum.loc["drawdown_12m", "status"] == "nonpositive_correlation"
    assert momentum.loc["distance_ma_12m", "selected"]
    rule_rows = monthly.loc[monthly.strategy.eq("momentum")]
    actual = apply_compounds(rule_rows, momentum.reset_index())["trend_drawdown"]
    expected = (rule_rows.z_market_return_24m + rule_rows.z_distance_ma_12m) / 2
    pd.testing.assert_series_equal(actual, expected, check_names=False, check_exact=True)


def test_notebook_selects_with_training_only_and_preserves_references(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    monthly = monthly_sample()
    report = {"min_history": 120, "first_target": REGIME_CPCV_START, "last_target": "1989-12", "parameters": {}}
    save_result(tmp_path, SCREENING_RESULTS[0], monthly, report)
    splits, cpcv_info = build_temporal_splits(calendar_start=REGIME_CPCV_START)
    save_result(tmp_path, REGIME_RESULT_NAMES[0], splits, {**cpcv_info, "min_history": 120})
    previous = tmp_path / "data/processed/walk_forward_120_metrics.parquet"
    previous.write_bytes(b"keep predictive reference")

    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("IPython.display.display", lambda *_: None)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    cell, = [c for c in notebook["cells"] if c["cell_type"] == "code" and "regime-compounds-120" in c["metadata"].get("tags", [])]
    assert cell["execution_count"] is None and not cell["outputs"]
    namespace = {}
    exec(compile("".join(cell["source"]), "14:regime-compounds-120", "exec"), namespace)
    tables = namespace["tablas_compuestos"]
    assert len(tables[RESULT_NAMES[0]]) == 55 * 32
    assert len(tables[RESULT_NAMES[1]]) == 55 * 8 * len(RULES)
    values = tables[RESULT_NAMES[2]]
    assert set(values.role) == {"train", "validation"}
    assert values.target_period.between(REGIME_CPCV_START, "1989-12").all()
    for name in RESULT_NAMES:
        saved, info = read_result(tmp_path, name)
        pd.testing.assert_frame_equal(saved, tables[name], check_exact=True)
        assert info["min_history"] == 120
    assert previous.read_bytes() == b"keep predictive reference"

    held = splits.loc[splits.split_id.eq(1) & splits.role.eq("validation"), "target_period"]
    monthly.loc[monthly.target_period.isin(held), "anomaly_return"] += 50
    save_result(tmp_path, SCREENING_RESULTS[0], monthly, report)
    assert not any((tmp_path / f"data/processed/{name}.parquet").exists() for name in RESULT_NAMES)
    assert previous.read_bytes() == b"keep predictive reference"
    changed, _ = run_regime_compounds(tmp_path)
    for name in RESULT_NAMES:
        first = lambda table: table.loc[table.validation_scheme.eq("CPCV") & table.split_id.eq(1)]
        pd.testing.assert_frame_equal(first(tables[name]), first(changed[name]), check_exact=True)
