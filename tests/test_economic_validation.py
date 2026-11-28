"""Contraste temporal y enlace del inventario con cuentas guardadas."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tfm.data import save_result
from tfm.economic_validation import SHARPE_REFERENCES, TEST_INTERVAL, load_momentum_capital_gaps, paired_sharpe_test
from tfm.economics import ACCOUNT_LABELS, DECISION_POLICY, RESULT_NAMES
from tfm.logistic import VARIANT as INITIAL_LOGISTIC
from tfm.walk_forward import VARIANT as M1_VARIANT


def test_paired_sharpe_uses_sample_std_and_is_symmetric():
    rng = np.random.default_rng(11)
    raw = rng.normal(0.005, 0.035, size=(481, 2))
    pairs = raw[1:] + 0.4 * raw[:-1]
    estimate = paired_sharpe_test(pairs, repetitions=499)
    inverse = paired_sharpe_test(pairs[:, ::-1], repetitions=499)
    expected = np.sqrt(12) * pairs.mean(axis=0) / pairs.std(ddof=1, axis=0)
    assert estimate["sharpe_difference"] == pytest.approx(expected[0] - expected[1])
    assert estimate["ci_low"] == pytest.approx(-inverse["ci_high"])
    assert estimate["ci_high"] == pytest.approx(-inverse["ci_low"])
    assert estimate["p_value"] == inverse["p_value"]
    with pytest.raises(ValueError, match="bloques completos"):
        paired_sharpe_test(pairs[:-1])
    with pytest.raises(ValueError, match="error estándar"):
        paired_sharpe_test(pairs[:, [0, 0]])


def test_notebook_leaves_inputs_intact_and_matches_completed_origin(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    months = pd.period_range(*TEST_INTERVAL, freq="M").astype(str)
    rng = np.random.default_rng(42)
    accounts = pd.concat([pd.DataFrame({"strategy": name, "period": months, "rf_return": .002,
                                        "net_return": rng.normal(.005, .03, len(months))})
                          for name in ACCOUNT_LABELS], ignore_index=True)
    report = {"attempt": "econ", "experiment_status": "completed", "test_interval": TEST_INTERVAL,
              "decision_policy": DECISION_POLICY, "source_attempts": {"M0_M1": "a", "M2": "m2", "M3": "m3"}}
    save_result(tmp_path, RESULT_NAMES[1], accounts, report)
    history = tmp_path / "outputs/experiments"
    history.mkdir(parents=True)
    common = {"candidate_configurations_per_rule": 1, "strategies": ["momentum", "reversal"]}
    chronological = {**common, "test_interval": TEST_INTERVAL, "variant": M1_VARIANT}
    events = [{**chronological, "attempt": "a", "status": "started"},
              {**chronological, "attempt": "a", "status": "completed"},
              {**chronological, "attempt": "b", "status": "failed"},
              {**chronological, "attempt": "other", "variant": "other_period",
               "test_interval": ["1927-01", "1949-12"], "status": "completed"}]
    (history / "walk_forward_trials.jsonl").write_text("\n".join(map(json.dumps, events)))
    (history / "logistic_trials.jsonl").write_text(json.dumps({**common, "attempt": "c",
        "variant": INITIAL_LOGISTIC, "development": ["1927-01", "1989-12"], "status": "completed"}))
    (history / "cpcv_regime_trials.jsonl").write_text(json.dumps({**chronological, "attempt": "d",
        "candidate_configurations_per_rule": 0, "status": "completed"}))
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("IPython.display.display", lambda *_: None)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"
             and "economic-validation" in cell["metadata"].get("tags", [])]
    assert len(cells) == 3
    namespace = {}
    for cell in cells:
        assert cell["execution_count"] is None and not cell["outputs"]
        exec(compile("".join(cell["source"]), "14:economic-validation", "exec"), namespace)
    tables = namespace["contraste_economico"]
    assert len(tables["comparisons"]) == 3 and tables["comparisons"].months.eq(480).all()
    assert len(tables["decades"]) == 12 and tables["decades"].months.eq(120).all()
    inventory = tables["inventory"]
    assert set(inventory.variant) == {M1_VARIANT, INITIAL_LOGISTIC}
    m1 = inventory.loc[inventory.variant.eq(M1_VARIANT)]
    assert m1.attempts.tolist() == [2, 2] and m1.completed.tolist() == [1, 1]
    assert m1.latest_status.eq("failed").all() and m1.next_step.eq("Retornos disponibles").all()
    assert m1.source_attempt.eq("a").all()
    assert inventory.loc[inventory.variant.eq(INITIAL_LOGISTIC), "account"].isna().all()
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before

    accounts.loc[0, "period"] = "1949-12"
    save_result(tmp_path, RESULT_NAMES[1], accounts, report)
    with pytest.raises(ValueError, match="retornos completos de 1950–1989"):
        namespace["run_economic_validation"](tmp_path)


def test_notebook_reads_capital_gaps_in_a_clean_kernel(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    months = pd.period_range(*TEST_INTERVAL, freq="M").astype(str)
    episode = months.isin(["1987-10", "1987-11"])
    names = ("momentum_m1", *SHARPE_REFERENCES)
    candidate_returns = np.where(episode, .04, .01)
    accounts = []
    for index, name in enumerate(names):
        returns = candidate_returns if index == 0 else np.full(len(months), .001 * index)
        capital = 100 * np.cumprod(1 + returns)
        accounts.append(pd.DataFrame({"strategy": name, "period": months, "rf_return": .002,
            "net_return": returns, "capital_start": np.r_[100, capital[:-1]], "capital_end": capital}))
    accounts = pd.concat(accounts, ignore_index=True)
    report = {"attempt": "econ", "experiment_status": "completed", "test_interval": TEST_INTERVAL,
              "decision_policy": DECISION_POLICY}
    save_result(tmp_path, RESULT_NAMES[1], accounts, report)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("IPython.display.display", lambda *_: None)
    monkeypatch.setattr(plt, "show", lambda: None)
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/14_referencia_walk_forward.ipynb").read_text())
    cell, = [c for c in notebook["cells"] if c["cell_type"] == "code"
             and "momentum-capital-gap" in c["metadata"].get("tags", [])]
    assert cell["execution_count"] is None and not cell["outputs"]
    namespace = {}
    exec(compile("".join(cell["source"]), "14:momentum-capital-gap", "exec"), namespace)
    for index, name in enumerate(SHARPE_REFERENCES, start=1):
        monthly_gap = np.log1p(candidate_returns) - np.log1p(.001 * index)
        expected = np.cumsum(monthly_gap)
        np.testing.assert_allclose(namespace["brechas_capital"][name], expected)
        np.testing.assert_allclose(namespace["ax"].lines[index - 1].get_ydata(), np.r_[0, expected])
        assert namespace["aporte_1987"][name] == pytest.approx(monthly_gap[episode].sum())
    plt.close(namespace["fig"])
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before

    accounts.loc[0, "capital_end"] = 0
    save_result(tmp_path, RESULT_NAMES[1], accounts, report)
    with pytest.raises(ValueError, match="capitales mensuales positivos"):
        load_momentum_capital_gaps(tmp_path)
