"""Contraste M1 emparejado y publicación en un calendario de rotaciones reducido."""

import json
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("sklearn")

from tfm.cpcv_regime import RESULT_NAMES as CPCV_RESULTS, evaluate_cpcv_candidate
from tfm.data import read_result, save_result
from tfm.momentum_shadows import RESULT_NAMES, run_momentum_shadows
from tfm.validation import build_temporal_splits
from test_logistic import PARAMETERS, fixture_samples


def test_notebook_pairs_shadows_with_the_saved_cpcv_candidate(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _, _, samples = fixture_samples()
    splits, _ = build_temporal_splits()
    reference, _ = evaluate_cpcv_candidate(samples, splits, "M1")
    predictions = reference["predictions"].loc[lambda t: t.strategy.eq("momentum")]
    predictions = predictions.drop(columns="candidate_model").rename(columns={"probability_model": "probability_logistic"})
    baseline = reference["metrics"].loc[lambda t: t.strategy.eq("momentum") & t.aggregation.ne("common_period")].copy()
    baseline["model"] = baseline.model.map({"M0": "naive", "M1": "logistic"})
    report = {"attempt": "cpcv", "variant_attempts": {"M1": "m1"}, "parameters": PARAMETERS, "versions": {}}
    monkeypatch.setattr("tfm.momentum_shadows.load_momentum_shadow_inputs",
        lambda root: (samples, splits, predictions, baseline, report))
    monkeypatch.setattr("tfm.momentum_shadows.circular_shifts", lambda n: [36, n-36])
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr(plt, "show", lambda: None)
    path = Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb"
    notebook = json.loads(path.read_text())
    cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"
             and "momentum-shadows" in cell.get("metadata", {}).get("tags", [])]
    assert len(cells) == 2
    namespace = {}
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:momentum-shadows", "exec"), namespace)
    plt.close("all")
    shadows, info = read_result(tmp_path, RESULT_NAMES[0])
    comparison, _ = read_result(tmp_path, RESULT_NAMES[1])
    assert len(comparison) == 1 and comparison.comparison_available.item()
    assert shadows.shift_months.tolist() == [36, 677] and shadows.completed_fits.eq(15).all()
    assert shadows.strategy.eq("momentum").all() and shadows.naive_log_loss.nunique() == 1
    assert comparison.improvement_threshold_95.item() == shadows.log_loss_improvement.max()
    assert info["reference_attempt"] == "m1" and info["expected_fits"] == 30

    stale = predictions.copy()
    stale.loc[stale.index[0], "probability_logistic"] = .123
    monkeypatch.setattr("tfm.momentum_shadows.load_momentum_shadow_inputs",
        lambda root: (samples, splits, stale, baseline, report))
    with pytest.raises(ValueError, match="no reproduce las predicciones"):
        run_momentum_shadows(tmp_path)
    pd.testing.assert_frame_equal(read_result(tmp_path, RESULT_NAMES[0])[0], shadows, check_exact=True)
    save_result(tmp_path, CPCV_RESULTS[0], reference["predictions"], {})
    for name in RESULT_NAMES:
        with pytest.raises(ValueError, match="secciones 42–43"):
            read_result(tmp_path, name)
