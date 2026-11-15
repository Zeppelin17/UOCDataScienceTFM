"""Emparejamiento CPCV, resumen común y sección independiente del notebook 14."""

import json
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.cpcv_regime import (CANDIDATE_COLUMNS, RESULT_NAMES, evaluate_cpcv_candidate,
                              run_cpcv_regime, _common_period_metrics)
from tfm.data import read_result, save_result
from tfm.features import FEATURE_COLUMNS
from tfm.validation import build_temporal_splits, summarize_validation
from tfm.walk_forward import INTERACTION_COLUMN, build_interaction_feature
from test_logistic import PARAMETERS, fixture_samples


def test_cpcv_fit_does_not_use_held_labels_and_common_period_keeps_months():
    features, _, samples = fixture_samples()
    interaction = build_interaction_feature(features)
    samples = samples.merge(interaction[["target_period", INTERACTION_COLUMN]], on="target_period", validate="many_to_one")
    splits, _ = build_temporal_splits()
    original, _ = evaluate_cpcv_candidate(samples, splits, "M3")
    changed = samples.copy()
    held = splits.loc[splits.split_id.eq(1) & splits.role.eq("validation"), "target_period"]
    mask = changed.target_period.isin(held) & changed.sample_usable
    changed.loc[mask, "label"] = 1-changed.loc[mask, "label"]
    repeated, _ = evaluate_cpcv_candidate(changed, splits, "M3")
    pd.testing.assert_frame_equal(original["coefficients"].loc[lambda t: t.split_id.eq(1)],
                                  repeated["coefficients"].loc[lambda t: t.split_id.eq(1)], check_exact=True)
    pd.testing.assert_frame_equal(original["predictions"].loc[lambda t: t.split_id.eq(1)].drop(columns="label"),
                                  repeated["predictions"].loc[lambda t: t.split_id.eq(1)].drop(columns="label"), check_exact=True)
    monthly = original["monthly"]
    assert monthly.validation_appearances.eq(5).all() and monthly.available_model.eq(5).all()
    assert len(monthly) == int(samples.sample_usable.sum())
    common = original["metrics"].loc[lambda t: t.aggregation.eq("common_period") & t.model.eq("M3")]
    for row in common.itertuples(index=False):
        assert row.examples == int((samples.strategy.eq(row.strategy) & samples.sample_usable & samples.target_period.ge("1950-01")).sum())
    empty = monthly.iloc[:0].rename(columns={"probability_model": "probability_logistic"})
    scores = _common_period_metrics(empty)
    assert len(scores) == 4 and scores.examples.eq(0).all() and scores.status.eq("empty_validation").all()
    assert scores[["auc", "log_loss"]].isna().all().all()


def test_cpcv_notebook_section_without_walk_forward_inputs_and_dependencies(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    features, labels, samples = fixture_samples()
    splits, _ = build_temporal_splits()
    coverage = summarize_validation(splits, samples)
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    save_result(tmp_path, "validation_splits", splits, {})
    save_result(tmp_path, "validation_summary", coverage, {})
    processed = tmp_path/"data/processed"
    previous = processed/"walk_forward_metrics.parquet"
    previous.write_bytes(b"not an input of the CPCV branch")
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    namespace = {}
    notebook = json.loads((Path(__file__).parents[1]/"notebooks/14_referencia_walk_forward.ipynb").read_text())
    code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code" and "cpcv" in c.get("metadata", {}).get("tags", [])]
    assert code_cells
    for cell in code_cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:cpcv", "exec"), namespace)
    plt.close("all")
    assert previous.read_bytes() == b"not an input of the CPCV branch"
    assert not (processed/"logistic_predictions.parquet").exists()
    report = namespace["informe_cpcv"]
    assert report["experiment_status"] == "completed" and report["candidate_configurations_added_per_rule"] == 0
    expected = (int(samples.sample_usable.sum())*5*6, int(samples.sample_usable.sum())*6, 238, 930, 204)
    for name, length in zip(RESULT_NAMES, expected):
        table, info = read_result(tmp_path, name)
        assert len(table) == length and info["attempt"] == report["attempt"]
    metrics = namespace["metricas_cpcv"]
    assert set(metrics.model) == {"M0", *CANDIDATE_COLUMNS}
    assert len(metrics.loc[metrics.model.eq("M0")]) == 34
    for model, columns in CANDIDATE_COLUMNS.items():
        coefficients = namespace["tablas_cpcv"]["cpcv_regime_coefficients"].loc[lambda t: t.candidate_model.eq(model)]
        assert set(coefficients.term) == {"intercept", *columns}
    assert all(row["expected_partitions"] == 15 and row["majority_required"] == 8 for row in report["stability"])
    log = tmp_path/report["trial_log"]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["status"] for e in events] == ["started", "completed"]*6
    assert all(e["validation_scheme"] == "CPCV" and e["candidate_configurations_added_per_rule"] == 0 for e in events)
    files = {processed/f"{name}.{ext}": (processed/f"{name}.{ext}").read_bytes()
             for name in RESULT_NAMES for ext in ("parquet", "json")}
    def failed(*args, **kwargs):raise RuntimeError("Fallo CPCV simulado")
    monkeypatch.setattr("tfm.cpcv_regime.evaluate_cpcv_candidate", failed)
    with pytest.raises(RuntimeError, match="Fallo CPCV"):
        run_cpcv_regime(tmp_path)
    assert [json.loads(line)["status"] for line in log.read_text().splitlines()][-2:] == ["started", "failed"]
    assert all(p.read_bytes() == data for p, data in files.items())
    history = log.read_bytes()
    for name in ("screening_tests", "logistic_metrics", "walk_forward_metrics",
                 "walk_forward_interaction_metrics", "walk_forward_ablation_metrics"):
        save_result(tmp_path, name, pd.DataFrame({"fixture": [1]}), {})
        assert all(p.read_bytes() == data for p, data in files.items())
    for name, table, info in (("validation_splits", splits, {}), ("validation_summary", coverage, {}),
        ("labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS}),
        ("monthly_features", features, {"feature_columns": FEATURE_COLUMNS})):
        for path, data in files.items():path.write_bytes(data)
        save_result(tmp_path, name, table, info)
        assert not any(p.exists() for p in files) and log.read_bytes() == history
