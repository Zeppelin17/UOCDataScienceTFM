"""Cuentas manuales, operaciones independientes y recorrido del notebook de etiquetas."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tfm.data import (calculate_signals, prepare_french_data, prepare_return_components,
                      prepare_shiller_data, read_result, save_result)
from tfm.features import FEATURE_COLUMNS, build_monthly_features
from tfm.labels import LABEL_TOLERANCE, build_monthly_labels
from tfm.simulation import simulate_baselines
from tfm.sources.shiller import XLS_SIGNATURE
from test_features import inputs as feature_inputs
from test_return_components import french_zip
from test_shiller import workbook
from test_simulation import inputs


PARAMETERS = {"initial_capital": 100.0, "transaction_cost_rate": 0.001,
              "annual_borrow_rate": 0.01, "include_dividends": True}


def test_manual_labels_cash_ties_and_sensitivity_keep_dividends_and_borrow():
    components, signals = inputs([0.01, 0.001, -0.01, 0.0], dividends=[0.002] * 4,
                                 rf=[0.003] * 4, momentum=[1, 1, 1, 0], reversal=[-1, -1, -1, 0])
    table = build_monthly_labels(components, signals, PARAMETERS).set_index(["strategy", "target_period"])
    long = table.loc[("momentum", "1927-01")]
    short = table.loc[("reversal", "1927-03")]
    b = 100 / 1.001
    assert long.capital_end == pytest.approx(b * 1.012 * 0.999)
    assert long.cash_capital_end == pytest.approx(100.3) and long.label == 1
    assert table.loc[("momentum", "1927-02"), "label"] == 0  # Gana, pero menos que RF.
    assert short.capital_end == pytest.approx(b * (1 + .01 - .002 + .003 - .01 / 12 - .001 * .99))
    assert short.label == 1 and short.borrow_cost == pytest.approx(b * .01 / 12)
    assert short.net_return_no_transaction_cost == pytest.approx(.01 - .002 + .003 - .01 / 12)
    idle = table.loc[("momentum", "1927-04")]
    assert pd.isna(idle.label) and pd.isna(idle.label_no_transaction_cost) and pd.isna(idle.label_changed)
    assert idle.label_status == "no_trade_signal" and not idle.has_signal
    # Un mes que cubre costes parcialmente cambia de etiqueta, con los demás supuestos iguales.
    components, signals = inputs([.001], dividends=[0.0], rf=[0.0])
    row = build_monthly_labels(components, signals, PARAMETERS).query("strategy == 'momentum'").iloc[0]
    assert row.label == 0 and row.label_no_transaction_cost == 1 and row.label_changed
    components, signals = inputs([.003], dividends=[0.0], rf=[.003])
    row = build_monthly_labels(components, signals, {**PARAMETERS, "transaction_cost_rate": 0.0}).iloc[0]
    assert abs(row.excess_return) <= LABEL_TOLERANCE and row.label == 0


def test_isolated_months_future_independence_and_invalid_inputs():
    components, signals = inputs([.01, -.02, .03], dividends=[.002] * 3, rf=[.001] * 3)
    result = build_monthly_labels(components, signals, PARAMETERS)
    assert result.capital_start.eq(100).all() and result.asset_notional_end.eq(0).all()
    for i in range(3):
        one = simulate_baselines(components.iloc[i:i+1].reset_index(drop=True),
                                 signals.iloc[i:i+1].reset_index(drop=True), PARAMETERS)
        expected = one.query("strategy != 'buy_and_hold'").reset_index(drop=True)
        actual = result.loc[result.target_period.eq(components.period.iloc[i])].reset_index(drop=True)
        assert actual.capital_end.tolist() == pytest.approx(expected.capital_end.tolist())
    changed = components.copy(); changed.loc[2, "price_return"] = -.1
    after = build_monthly_labels(changed, signals, PARAMETERS)
    pd.testing.assert_frame_equal(result.loc[result.target_period.lt("1927-03")],
                                  after.loc[after.target_period.lt("1927-03")])
    bad = signals.copy(); bad.loc[0, "momentum_signal"] = pd.NA
    with pytest.raises(ValueError, match="ausente"):
        build_monthly_labels(components, bad, PARAMETERS)
    future_components, future_signals = components.copy(), signals.copy()
    future_components.loc[2, "period"] = "1990-01"
    with pytest.raises(ValueError, match="1927–1989"):
        build_monthly_labels(future_components, future_signals, PARAMETERS)
    insolvent, proposed = inputs([1.2])
    with pytest.raises(ValueError, match="insolvente"):
        build_monthly_labels(insolvent, proposed, PARAMETERS)  # No eliminar un resultado desfavorable.


def test_notebook_persistence_stale_features_and_dependency_invalidations(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    workbook(monkeypatch)
    shiller = tmp_path / "original.xls"; shiller.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "original.zip"
    french.write_bytes(french_zip([f"{m.replace('-', '')},unused,unused,unused,0.20"
                                   for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepare_shiller_data(tmp_path, file=shiller); calculate_signals(tmp_path)
    prepare_french_data(tmp_path, file=french); prepare_return_components(tmp_path)
    features = build_monthly_features(*feature_inputs())
    report = {"feature_columns": FEATURE_COLUMNS}
    save_result(tmp_path, "monthly_features", features, report)
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    monkeypatch.setattr("tfm.sources.french.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/08_etiquetas.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "08_etiquetas.ipynb", "exec"), namespace)
    path = tmp_path / "data/processed/labelled_signals.parquet"
    dataset = pd.read_parquet(path)
    info = json.loads(path.with_suffix(".json").read_text())
    assert len(dataset) == info["rows"] == 1512
    assert dataset.label.isna().all() and not dataset.training_ready.any()  # Precios sintéticos constantes.
    assert dataset.features_ready.sum() == 1498
    assert info["feature_columns"] == FEATURE_COLUMNS and len(info["definitions"]) == 2
    assert all(row["training_examples"] == 0 for row in info["strategies"])
    feature_path = tmp_path / "data/processed/monthly_features.parquet"
    good = feature_path.read_bytes()
    features.rename(columns={"market_return_24m": "distance_ma_3m"}).to_parquet(feature_path, index=False)
    with pytest.raises(ValueError, match="notebook 07"):
        read_result(tmp_path, "monthly_features")
    feature_path.write_bytes(good)
    saved = {p: p.read_bytes() for p in (path, path.with_suffix(".json"))}
    for regenerate in (calculate_signals, prepare_return_components, prepare_french_data, prepare_shiller_data):
        for p, content in saved.items():p.write_bytes(content)
        regenerate(tmp_path)
        assert not path.exists() and not path.with_suffix(".json").exists()
    for p, content in saved.items():p.write_bytes(content)
    save_result(tmp_path, "monthly_features", features, report)
    assert not path.exists() and not path.with_suffix(".json").exists()
