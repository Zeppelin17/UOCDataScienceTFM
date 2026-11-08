"""Calendario y fronteras; ejemplos, recorrido sin red e invalidación de salidas."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tfm.data import (calculate_signals, prepare_french_data, prepare_return_components,
                      prepare_shiller_data, read_result, save_result)
from tfm.features import FEATURE_COLUMNS
from tfm.sources.shiller import XLS_SIGNATURE
from tfm.validation import (MODEL_COLUMNS, RESULT_NAMES, build_temporal_splits,
                            prepare_validation_samples, summarize_validation)
from test_return_components import french_zip
from test_screening import linear_features
from test_shiller import workbook


PARAMETERS = {"initial_capital": 100.0, "transaction_cost_rate": .001,
              "annual_borrow_rate": .01, "include_dividends": True}


def test_fixed_blocks_purge_embargo_and_inclusive_label_intervals():
    splits, report = build_temporal_splits()
    assert len(splits) == 11340 and len(report["partitions"]) == 15
    assert len(splits[["validation_block_1", "validation_block_2"]].drop_duplicates()) == 15
    assert splits.groupby("split_id").size().eq(756).all()
    assert splits.loc[splits.role.eq("validation")].groupby("target_period").size().eq(5).all()
    assert [(b["first_target"], b["last_target"]) for b in report["blocks"]] == [
        ("1927-01", "1937-06"), ("1937-07", "1947-12"), ("1948-01", "1958-06"),
        ("1958-07", "1968-12"), ("1969-01", "1979-06"), ("1979-07", "1989-12")]
    assert all(b["months"] == 126 for b in report["blocks"])
    # Partición 2: validación en bloques 1 y 3, con el calendario completo.
    selected = splits.loc[splits.split_id.eq(2)].set_index("target_period")
    assert selected.loc["1947-11", "role"] == "train"
    assert selected.loc["1947-12", "role"] == "purge"
    assert selected.loc["1948-01":"1958-06", "role"].eq("validation").all()
    assert selected.loc["1958-07", "role"] == "purge"
    assert selected.loc["1958-07", "in_embargo_window"]
    assert selected.loc["1958-08":"1958-12", "role"].eq("embargo").all()
    assert selected.loc["1959-01", "role"] == "train"  # No añadir un séptimo mes.
    # Los bloques 1 y 2 se fusionan: no aparecen exclusiones en su frontera interior.
    first = splits.loc[splits.split_id.eq(1)].set_index("target_period")
    assert first.loc["1937-06":"1937-07", "role"].eq("validation").all()
    assert first.loc["1948-01", "role"] == "purge"
    assert first.loc["1948-02":"1948-06", "role"].eq("embargo").all()
    assert len(report["partitions"][0]["validation_intervals"]) == 1
    last = splits.loc[splits.split_id.eq(15)]
    assert not last.in_embargo_window.any() and last.role.eq("purge").sum() == 1
    for item in report["partitions"]:
        part = splits.loc[splits.split_id.eq(item["split_id"])]
        assert part.role.eq("validation").sum() == 252
        train = pd.PeriodIndex(part.loc[part.role.eq("train"), "target_period"], freq="M")
        for interval in item["validation_intervals"]:
            start, end = pd.Period(interval["start"], freq="M"), pd.Period(interval["end"], freq="M")
            # [t-1, t] del entrenamiento no toca [inicio-1, fin] de la validación.
            assert ((train < start - 1) | (train - 1 > end)).all()
            assert not ((train > end) & (train <= end + 6)).any()


def test_samples_notebook_persistence_and_upstream_invalidations(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)
    features = linear_features()
    features.loc[:6, "industry_breadth_12m"] = np.nan
    features["features_ready"] = features[FEATURE_COLUMNS].notna().all(axis=1)
    i = np.arange(len(features))
    pieces = []
    for rule, signal in (("momentum", i % 3 != 0), ("reversal", i % 5 != 0)):
        part = features.copy()
        part["strategy"] = rule
        part["has_signal"] = signal
        part["label_end_period"] = part.target_period
        part["label"] = pd.array(i % 2, dtype="Int8")
        part.loc[~signal, "label"] = pd.NA
        part["label_no_transaction_cost"] = part.label.copy()
        part["training_ready"] = part.features_ready & part.has_signal
        part["excess_return"] = np.where(signal, np.where(i % 2, .01, -.01), 0.0)
        pieces.append(part)
    labels = pd.concat(pieces, ignore_index=True)
    samples, preparation = prepare_validation_samples(features, labels)
    assert len(samples) == 1512 and preparation["causal_common_months"] == 713
    assert preparation["first_causal_target"] == "1930-08" and len(MODEL_COLUMNS) == 10
    assert not samples.loc[~samples.has_signal, "sample_usable"].any()
    splits, _ = build_temporal_splits()
    summary = summarize_validation(splits, samples)
    assert len(summary) == 30
    assert summary.train_classifier_ready.all() and summary.validation_auc_estimable.all()
    assert (summary.train_positive + summary.train_negative).equals(summary.train_examples)
    assert (summary.validation_positive + summary.validation_negative).equals(summary.validation_examples)
    # Una clase única no cambia fechas ni disponibilidad: se conserva y se marca.
    changed = labels.copy(); changed.loc[changed.has_signal, "label"] = 0
    after, _ = prepare_validation_samples(features, changed)
    pd.testing.assert_frame_equal(samples.drop(columns="label"), after.drop(columns="label"))
    constant = summarize_validation(splits, after)
    assert len(constant) == 30 and not constant.train_classifier_ready.any() and not constant.validation_auc_estimable.any()
    pd.testing.assert_frame_equal(summary[["train_calendar_months", "validation_calendar_months", "train_examples", "validation_examples"]],
                                  constant[["train_calendar_months", "validation_calendar_months", "train_examples", "validation_examples"]])
    bad = labels.copy(); bad.loc[0, "label_end_period"] = "1990-01"
    with pytest.raises(ValueError, match="1927–1989"):
        prepare_validation_samples(features, bad)
    bad = labels.copy(); bad.loc[bad.has_signal.idxmax(), "label"] = pd.NA
    with pytest.raises(ValueError, match="señal activa"):
        prepare_validation_samples(features, bad)
    bad = labels.copy(); bad.loc[~bad.has_signal, "label"] = 0
    with pytest.raises(ValueError, match="efectivo"):
        prepare_validation_samples(features, bad)
    bad = labels.copy(); bad.loc[0, "market_return_24m"] = -99.0
    with pytest.raises(ValueError, match="no coinciden"):
        prepare_validation_samples(features, bad)
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No descargar"))
    monkeypatch.setattr("tfm.sources.french.urlopen", lambda *a, **k: pytest.fail("No descargar"))
    monkeypatch.setattr("tfm.diagnostics.urlopen", lambda *a, **k: pytest.fail("No descargar contexto"))
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/10_validacion_temporal.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "10_validacion_temporal.ipynb", "exec"), namespace)
    plt.close("all")
    paths = [tmp_path / "data/processed" / f"{name}.{ext}" for name in RESULT_NAMES for ext in ("parquet", "json")]
    for name, count in (("validation_splits", 11340), ("validation_summary", 30)):
        path = tmp_path / "data/processed" / f"{name}.parquet"
        info = json.loads(path.with_suffix(".json").read_text())
        assert info["rows"] == len(pd.read_parquet(path)) == count
        assert info["scope"] == "development_partition_preparation_only" and info["embargo_months"] == 6
        assert info["model_columns"] == MODEL_COLUMNS
    before = {path: path.read_bytes() for path in paths}
    # Los resultados del cribado son independientes de las particiones.
    save_result(tmp_path, "screening_tests", pd.DataFrame({"fixture": [1]}), {})
    assert all(path.read_bytes() == content for path, content in before.items())
    for name, table, report in (("monthly_features", features, {"feature_columns": FEATURE_COLUMNS}),
                               ("labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})):
        for path, content in before.items():path.write_bytes(content)
        save_result(tmp_path, name, table, report)
        assert not any(path.exists() for path in paths)
    # Preparación sintética mínima para comprobar también las dependencias de 01/02.
    workbook(monkeypatch)
    shiller = tmp_path / "fixture.xls"; shiller.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "fixture.zip"
    french.write_bytes(french_zip([f"{month.replace('-', '')},unused,unused,unused,0.20"
                        for month in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepare_shiller_data(tmp_path, file=shiller); calculate_signals(tmp_path)
    prepare_french_data(tmp_path, file=french); prepare_return_components(tmp_path)
    for regenerate in (prepare_shiller_data, calculate_signals, prepare_french_data, prepare_return_components):
        for path, content in before.items():path.write_bytes(content)
        regenerate(tmp_path)
        assert not any(path.exists() for path in paths)
