"""Recorrido real de las celdas de preparación y simulación, sin red ni gráficos."""

import json
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from tfm.data import (calculate_signals, prepare_french_data, prepare_return_components,
                      prepare_shiller_data, read_result)
from tfm.sources.shiller import XLS_SIGNATURE
from test_return_components import french_zip
from test_shiller import workbook


NOTEBOOKS = Path(__file__).parents[1] / "notebooks"


def test_notebooks_without_configuration_and_upstream_invalidations(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    pytest.importorskip("IPython")
    workbook(monkeypatch)
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    (raw / "shiller.xls").write_bytes(XLS_SIGNATURE + b"synthetic")
    (raw / "french_factors.zip").write_bytes(french_zip([
        f"{m.replace('-', '')},unused,unused,unused,0.20"
        for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)
    ]))
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    monkeypatch.setattr("tfm.sources.french.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    products = {3: ("baseline_simulations", 2268), 4: ("baseline_sensitivity", 21),
                5: ("bear_filter_simulations", 3780), 6: ("simple_comparisons", 6048)}
    for number in range(1, 7):
        notebook = json.loads(next(NOTEBOOKS.glob(f"{number:02d}_*.ipynb")).read_text())
        cells = (2, 5, 7) if number == 1 else (2, 4)
        namespace = {"display": lambda *a, **k: None}
        for index in cells:
            exec(compile("".join(notebook["cells"][index]["source"]), f"notebook_{number}_{index}", "exec"), namespace)
        if number in products:
            name, count = products[number]
            table, report = read_result(tmp_path, name)
            assert len(table) == count and report["last_period"] == "1989-12"
            assert report["parameters"]["transaction_cost_rate"] == 0.001
    basic, _ = read_result(tmp_path, "baseline_simulations")
    joint, _ = read_result(tmp_path, "simple_comparisons")
    assert_frame_equal(basic, joint.loc[joint.strategy.isin(basic.strategy.unique()), basic.columns].reset_index(drop=True), check_dtype=False)
    assert not (tmp_path / "configs").exists()
    paths = [tmp_path / "data/processed" / f"{name}.{suffix}"
             for name, _ in products.values() for suffix in ("parquet", "json")]
    saved = {path: path.read_bytes() for path in paths}
    for regenerate in (calculate_signals, prepare_return_components, prepare_french_data, prepare_shiller_data):
        for path, content in saved.items():
            path.write_bytes(content)
        regenerate(tmp_path)
        assert all(not path.exists() for path in paths)
