"""Verificación de DSR, rangos CSCV y recorrido independiente del notebook."""

from itertools import combinations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tfm.data import read_result, save_result
from tfm.economic_validation import TEST_INTERVAL
from tfm.overfitting import PBO_BLOCKS, RESULT_NAMES, combinatorial_pbo, deflated_sharpe
from tfm.selection_returns import FILTERS, REFERENCES, RESULT_NAME


def test_dsr_uses_monthly_sharpe_and_accounts_for_correlated_trials():
    scipy = pytest.importorskip("scipy.stats")
    a = np.array([-.032, -.014, -.009, .002, .008, .027, .042, .087])
    b = a + .01
    result = deflated_sharpe(pd.DataFrame({"A": a, "B": b}))
    assert result.trials_used.tolist() == [1, 1]
    assert result.benchmark_annualized.eq(0).all()
    expected = []
    for returns in (a, b):
        sharpe = returns.mean() / returns.std(ddof=1)
        error = np.sqrt((1 - scipy.skew(returns) * sharpe
                         + (scipy.kurtosis(returns, fisher=False) - 1) * sharpe**2 / 4) / (len(a) - 1))
        expected.append(scipy.norm.cdf(sharpe / error))
    np.testing.assert_allclose(result.dsr, expected, atol=1e-14, rtol=0)
    assert (result.dsr_all_independent < result.dsr).all()

    uncorrelated = pd.DataFrame({"A": [.06, .01, .06, .01], "B": [.04, .04, .02, .02]})
    equal_benchmarks = deflated_sharpe(uncorrelated)
    assert equal_benchmarks.trials_used.eq(2).all()
    np.testing.assert_array_equal(equal_benchmarks.dsr, equal_benchmarks.dsr_all_independent)


def test_pbo_matches_enumeration_and_uses_fixed_tie_break():
    rng = np.random.default_rng(42)
    returns = pd.DataFrame(rng.normal(.002, .03, (16, 3)), columns=["C", "B", "A"])
    summary, detail = combinatorial_pbo(returns, blocks=4)
    expected_ranks, expected_choices = [], []
    chunks = np.array_split(returns.sort_index(axis=1).to_numpy(), 4, axis=0)
    for training in combinations(range(4), 2):
        first = np.concatenate([chunks[i] for i in training])
        second = np.concatenate([chunks[i] for i in range(4) if i not in training])
        best = int((first.mean(axis=0) / first.std(ddof=1, axis=0)).argmax())
        complement = pd.Series(second.mean(axis=0) / second.std(ddof=1, axis=0))
        expected_choices.append(["A", "B", "C"][best])
        expected_ranks.append(complement.rank(method="average").iloc[best])
    assert detail.selected_policy.tolist() == expected_choices
    assert detail.complement_rank.tolist() == expected_ranks
    assert detail.at_median.tolist() == [rank == 2 for rank in expected_ranks]
    assert summary["pbo"] == sum(rank < 2 for rank in expected_ranks) / 6

    values = np.tile([.007, .009, .01, .013], 4)
    tied = pd.DataFrame({"Z": values, "B": values - .02, "A": values})
    summary, detail = combinatorial_pbo(tied, blocks=4)
    assert summary["selection_tie_splits"] == 6 and summary["pbo"] == 0
    assert detail.selected_policy.eq("A").all() and detail.complement_rank.eq(2.5).all()


def test_notebook_publishes_controls_linked_to_the_matrix(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    months = pd.period_range(*TEST_INTERVAL, freq="M").astype(str)
    rng = np.random.default_rng(41)
    matrix = pd.concat([pd.DataFrame({"rule": rule, "role": role, "policy": name, "period": months,
                                    "net_return": rng.normal(.004, .022, len(months)), "rf_return": .002})
                        for rule in ("momentum", "reversal")
                        for role, names in (("candidate", FILTERS), ("reference", REFERENCES))
                        for name in names], ignore_index=True)
    report = {"attempt": "matrix-development", "test_interval": TEST_INTERVAL}
    save_result(tmp_path, RESULT_NAME, matrix, report)
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("IPython.display.display", lambda *_: None)
    monkeypatch.setattr(plt, "show", lambda: None)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"
             and "overfitting" in c["metadata"].get("tags", [])]
    assert len(cells) == 3
    namespace = {}
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:overfitting", "exec"), namespace)
    plt.close("all")
    for name, rows in zip(RESULT_NAMES, (32, 2, 25740), strict=True):
        saved, info = read_result(tmp_path, name)
        assert len(saved) == rows and info["pbo_blocks"] == PBO_BLOCKS
        assert info["source_attempt"] == report["attempt"]
        pd.testing.assert_frame_equal(saved, namespace["tablas_sobreajuste"][name], check_exact=True)
    save_result(tmp_path, RESULT_NAME, matrix, {**report, "attempt": "new-matrix"})
    for name in RESULT_NAMES:
        with pytest.raises(ValueError, match="Faltan DSR y PBO"):
            read_result(tmp_path, name)
