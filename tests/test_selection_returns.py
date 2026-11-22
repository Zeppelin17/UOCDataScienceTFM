"""Matriz completa con umbral fijo y publicación dependiente de sus entradas."""

import json
from pathlib import Path

import pandas as pd
import pytest

from test_economics import economic_inputs
from tfm.data import read_result, save_result
from tfm.economics import MODEL_PROBABILITIES, RESULT_NAMES, evaluate_economics
from tfm.selection_returns import FILTERS, REFERENCES, RESULT_NAME, build_selection_returns


def selection_inputs():
    monthly, signals, components, predictions, parameters, _ = economic_inputs()
    tables, _ = evaluate_economics(monthly, signals, components, predictions, parameters)
    forecasts = predictions.assign(**{name: .65 for name in FILTERS})
    for name in ("M1", "M2", "M3"):
        forecasts[f"L2_{name}"] = predictions[MODEL_PROBABILITIES[name]]
    return signals, components, forecasts, parameters, tables[RESULT_NAMES[1]]


def test_complete_aligned_matrix_and_no_imputation_of_active_predictions():
    signals, components, forecasts, parameters, accounts = selection_inputs()
    matrix = build_selection_returns(signals, components, forecasts, parameters, accounts)
    assert len(matrix) == 2 * (len(FILTERS) + len(REFERENCES)) * 480
    assert not matrix.duplicated(["rule", "policy", "period"]).any()
    m1 = matrix.loc[matrix.rule.eq("momentum") & matrix.policy.eq("L2_M1")]
    previous = accounts.loc[accounts.strategy.eq("momentum_m1")]
    pd.testing.assert_series_equal(m1.net_return.reset_index(drop=True),
                                   previous.net_return.reset_index(drop=True), check_exact=True)
    forecasts.loc[0, "GB_M2"] = float("nan")
    with pytest.raises(ValueError, match="probabilidades finitas"):
        build_selection_returns(signals, components, forecasts, parameters, accounts)


def test_notebook_publishes_and_invalidates_matrix_with_its_inputs(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    inputs = selection_inputs()
    candidates = {name: {} for name in FILTERS}
    monkeypatch.setattr("tfm.selection_returns.load_selection_inputs", lambda _: (*inputs, candidates, "econ"))
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("IPython.display.display", lambda *_: None)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"
             and "selection-returns" in c["metadata"].get("tags", [])]
    assert len(cells) == 2
    namespace = {}
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:selection-returns", "exec"), namespace)
    matrix, report = read_result(tmp_path, RESULT_NAME)
    pd.testing.assert_frame_equal(matrix, namespace["matriz_economica"], check_exact=True)
    assert report["economic_reference_attempt"] == "econ"
    with pytest.raises(ValueError, match="sin duplicados"):
        save_result(tmp_path, RESULT_NAME, pd.concat([matrix, matrix.iloc[:1]], ignore_index=True), report)
    pd.testing.assert_frame_equal(matrix, read_result(tmp_path, RESULT_NAME)[0], check_exact=True)
    save_result(tmp_path, "mda_logistic_metrics", pd.DataFrame({"test": [1]}), {})
    assert read_result(tmp_path, RESULT_NAME)[1]["attempt"] == report["attempt"]
    save_result(tmp_path, "ebm_walk_forward_predictions", pd.DataFrame({"test": [1]}), {})
    with pytest.raises(ValueError, match="Faltan las series"):
        read_result(tmp_path, RESULT_NAME)
