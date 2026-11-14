"""Rotación conjunta y recorrido sintético del contraste de sombras del modelo."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.data import read_result, save_result
from tfm.features import FEATURE_COLUMNS
from tfm.logistic import run_logistic_experiment
from tfm.model_shadows import (RESULT_NAMES, circular_shadow, circular_shifts,
                               compare_shadows, model_calendar, run_model_shadows)
from tfm.validation import MODEL_COLUMNS, build_temporal_splits, summarize_validation
from test_logistic import PARAMETERS, fixture_samples


def test_joint_rotation_keeps_months_labels_masks_and_both_rules():
    _, _, samples = fixture_samples()
    before = samples.copy(deep=True)
    calendar = model_calendar(samples)
    assert len(calendar) == 713
    shifts = circular_shifts(len(calendar))
    assert len(shifts) == 642 and shifts[0] == 36 and shifts[-1] == 677
    assert all(min(s, len(calendar) - s) >= 36 for s in shifts)
    moved = circular_shadow(samples, 36)
    pd.testing.assert_frame_equal(samples, before, check_exact=True)
    pd.testing.assert_frame_equal(samples.drop(columns=MODEL_COLUMNS), moved.drop(columns=MODEL_COLUMNS), check_exact=True)
    for rule in ("momentum", "reversal"):
        mask = samples.strategy.eq(rule) & samples.causal_features_ready
        np.testing.assert_array_equal(moved.loc[mask, MODEL_COLUMNS],
                                      np.roll(calendar[MODEL_COLUMNS].to_numpy(), 36, axis=0))
    pd.testing.assert_frame_equal(samples.loc[~samples.causal_features_ready], moved.loc[~moved.causal_features_ready])
    assert samples.loc[samples.causal_features_ready & samples.strategy.eq("momentum"), "has_signal"].eq(False).any()
    for invalid in (0, 35, 678, 713, True):
        with pytest.raises(ValueError, match="distancia circular"):
            circular_shadow(samples, invalid)


def test_notebook_small_shadow_schedule_thresholds_history_and_invalidations(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    features, labels, samples = fixture_samples()
    splits, _ = build_temporal_splits()
    summary = summarize_validation(splits, samples)
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    save_result(tmp_path, "validation_splits", splits, {})
    save_result(tmp_path, "validation_summary", summary, {})
    original_tables, original_report = run_logistic_experiment(tmp_path)
    for name, table in original_tables.items():
        save_result(tmp_path, name, table, original_report)
    original_paths = [tmp_path / "data/processed" / f"{name}.{ext}"
                      for name in original_tables for ext in ("parquet", "json")]
    original_paths.append(tmp_path / "outputs/experiments/logistic_trials.jsonl")
    before = {p: p.read_bytes() for p in original_paths}
    # Solo el calendario de rotaciones se simula: ambos desplazamientos ajustan
    # realmente las quince particiones por regla y usan sus métricas originales.
    monkeypatch.setattr("tfm.model_shadows.circular_shifts", lambda n: [36, n - 36])
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/12_sombras_logistica.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "12_sombras_logistica.ipynb", "exec"), namespace)
    plt.close("all")
    assert all(p.read_bytes() == content for p, content in before.items())
    shadows, info = read_result(tmp_path, "logistic_shadows")
    comparison, _ = read_result(tmp_path, "logistic_shadow_comparison")
    assert len(shadows) == 4 and len(comparison) == 2 and comparison.comparison_available.all()
    assert shadows.completed_fits.eq(15).all()
    assert info["candidate_configurations_added"] == 0 and info["expected_fits"] == 60
    assert info["original_attempt"] == original_report["attempt"]
    assert info["auc_shadow_role"] == "descriptive_only"
    for row in comparison.itertuples():
        assert row.improvement_threshold_95 == shadows.loc[shadows.strategy.eq(row.strategy), "log_loss_improvement"].max()

    # Valores binarios exactos: el empate con el percentil no supera el umbral.
    manual = shadows.copy()
    manual["log_loss_improvement"] = [.125, 0., .25, .125]
    manual["naive_log_loss"] = 1.
    manual["log_loss"] = 1. - manual.log_loss_improvement
    manual["auc"] = [.5, .5, .6, .6]
    original = original_tables["logistic_metrics"].copy()
    original.loc[original.model.eq("naive"), "log_loss"] = 1.
    original.loc[original.model.eq("logistic"), "log_loss"] = .75
    original.loc[original.model.eq("logistic"), "auc"] = .6
    calculated, status = compare_shadows(manual, original, [36, 677])
    assert status["shadow_comparison_available"]
    assert calculated.improvement_threshold_95.tolist() == [.25, .125]
    assert calculated.meets_operational_criterion.tolist() == [False, True]
    for incomplete in (manual.iloc[:-1], manual.assign(auc=[np.nan, .5, .6, .6])):
        calculated, status = compare_shadows(incomplete, original, [36, 677])
        assert not status["shadow_comparison_available"] and not calculated.comparison_available.any()
        assert calculated.improvement_threshold_95.isna().all()
        assert calculated.meets_operational_criterion.isna().all()

    log = tmp_path / info["trial_log"]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["status"] for e in events] == ["started", "completed"]
    assert all(e["purpose"] == "circular_shadow_reference" for e in events)
    def failed(*args):
        raise RuntimeError("Fallo de sombra simulado")
    monkeypatch.setattr("tfm.model_shadows.evaluate_logistic", failed)
    with pytest.raises(RuntimeError, match="Fallo de sombra"):
        run_model_shadows(tmp_path)
    assert all(p.read_bytes() == content for p, content in before.items())
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["status"] for e in events] == ["started", "completed", "started", "failed"]
    assert events[-1]["shift_months_at_failure"] == 36
    saved = {tmp_path / "data/processed" / f"{name}.{ext}":
             (tmp_path / "data/processed" / f"{name}.{ext}").read_bytes()
             for name in RESULT_NAMES for ext in ("parquet", "json")}
    save_result(tmp_path, "screening_tests", pd.DataFrame({"fixture": [1]}), {})
    assert all(p.read_bytes() == data for p, data in saved.items())
    history = log.read_bytes()
    regenerations = [(name, table, original_report) for name, table in original_tables.items()]
    regenerations += [("validation_splits", splits, {}), ("monthly_features", features, {})]
    for name, table, report in regenerations:
        for path, content in saved.items():path.write_bytes(content)
        save_result(tmp_path, name, table, report)
        assert not any(p.exists() for p in saved) and log.read_bytes() == history
