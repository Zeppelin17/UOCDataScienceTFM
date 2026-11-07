"""Tres comprobaciones: causalidad, estadística conocida y recorrido persistido sin red."""

import json
from pathlib import Path
from statistics import stdev

import numpy as np
import pandas as pd
import pytest

from tfm.data import (calculate_signals, prepare_french_data, prepare_return_components,
                      prepare_shiller_data, read_result, save_result)
from tfm.features import FEATURE_COLUMNS, build_monthly_features
from tfm.labels import build_monthly_labels
from tfm.screening import (RESULT_NAMES, build_screening_monthly, describe_regimes,
                           hac_regression, holm_adjust, screen_relationships, transform_features)
from tfm.simulation import simulate_baselines
from tfm.sources.shiller import INSTRUMENT, XLS_SIGNATURE
from test_features import inputs as feature_inputs
from test_return_components import french_zip
from test_shiller import workbook


PARAMETERS = {"initial_capital": 100.0, "transaction_cost_rate": .001,
              "annual_borrow_rate": .01, "include_dividends": True}


def linear_features():
    months = pd.period_range("1927-01", "1989-12", freq="M")
    return pd.DataFrame({"asset": INSTRUMENT, "target_period": months.astype(str),
                         "decision_period": (months - 1).astype(str),
                         "price_source_period": (months - 1).astype(str),
                         "context_source_period": (months - 2).astype(str),
                         **{name: np.arange(len(months), dtype=float) for name in FEATURE_COLUMNS}})


def test_causal_winsorization_warmup_ties_and_date_alignment():
    features = linear_features()
    transformed, report = transform_features(features)
    # Para los 36 valores anteriores 0..35: límites .35 y 34.65; media 17.5.
    expected = (34.65 - 17.5) / stdev([.35, *range(1, 35), 34.65])
    assert transformed.loc[36, "z_price_return_1m"] == pytest.approx(expected)
    assert not transformed.loc[:35, "screening_ready"].any()
    assert transformed.loc[36:, "screening_ready"].all() and len(report["excluded_targets"]) == 36
    changed = features.copy()
    changed.loc[100:, FEATURE_COLUMNS] = 1e6
    after, _ = transform_features(changed)
    pd.testing.assert_frame_equal(transformed.iloc[:100], after.iloc[:100])
    # Cambiar el valor actual no cambia sus límites: ambos extremos altos quedan recortados igual.
    changed.loc[36, FEATURE_COLUMNS] = 1e6
    after, _ = transform_features(changed)
    assert after.loc[36, "z_price_return_1m"] == pytest.approx(expected)
    missing = features.copy(); missing.loc[:6, "industry_breadth_12m"] = np.nan
    actual, _ = transform_features(missing)
    assert actual.loc[43, "screening_ready"] and not actual.loc[:42, "screening_ready"].any()
    tied = features.copy(); tied.loc[:36, "credit_spread_pp"] = 7.0
    actual, _ = transform_features(tied)
    assert pd.isna(actual.loc[36, "z_credit_spread_pp"])
    assert actual.loc[36, "tercile_credit_spread_pp"] == 2  # No separar empates.
    assert "constant_history" in actual.loc[36, "exclusion_reason"]
    missing.loc[100, "industry_breadth_12m"] = np.nan
    with pytest.raises(ValueError, match="huecos"):
        transform_features(missing)
    bad = features.copy(); bad.loc[0, "context_source_period"] = "1926-12"
    with pytest.raises(ValueError, match="alineadas"):
        transform_features(bad)


def test_known_hac_holm_and_joint_circular_shadows():
    # Referencia calculada con aritmética racional y el sandwich matricial completo 2x2.
    # Var(b) exacta: 121354813 / 70251148968, sin factor n/(n-2).
    fit = hac_regression(range(12), [1, 2, 1, 4, 3, 6, 4, 8, 7, 9, 8, 12])
    assert fit["intercept"] == pytest.approx(17/39)
    assert fit["slope"] == pytest.approx(259/286)
    assert fit["standard_error"] == pytest.approx(.04156251189049109)
    assert fit["t_hac"] == pytest.approx(21.7887313447384)
    assert fit["p_value"] == pytest.approx(2.9675843783242883e-105, rel=1e-9, abs=0)
    assert not hac_regression(np.ones(12), np.arange(12))["estimable"]
    assert not hac_regression(np.arange(12), np.arange(12))["estimable"]
    with pytest.raises(ValueError, match="finitas"):
        hac_regression([np.nan], [0.0])
    p = [.04, .002, .03, .01, .2, *([1.0] * 15)]
    assert holm_adjust(p) == pytest.approx([.68, .04, .54, .19, 1, *([1] * 15)])
    months = pd.period_range("1927-01", periods=100, freq="M").astype(str)
    i = np.arange(100)
    pieces = []
    for rule, y in (("momentum", np.sin(i/6) + np.cos(i/17)),
                    ("reversal", np.cos(i/7) - np.sin(i/12))):
        pieces.append(pd.DataFrame({"strategy": rule, "target_period": months,
            "screening_ready": True, "anomaly_return": y, "has_signal": True,
            **{f"z_{f}": np.sin(i/(j+3)) + .01*i for j, f in enumerate(FEATURE_COLUMNS)},
            **{f"tercile_{f}": 1 + i % 3 for f in FEATURE_COLUMNS}}))
    monthly = pd.concat(pieces, ignore_index=True)
    tests, shadows, report = screen_relationships(monthly)
    assert len(tests) == 20 and shadows.shift_months.tolist() == list(range(36, 65))
    assert shadows.circular_distance_months.min() == 36
    assert shadows.estimable_tests.eq(20).all()
    assert report["shadow_threshold_95"] == np.quantile(shadows.max_abs_t_hac, .95, method="higher")
    expected_max = max(abs(hac_regression(np.roll(part[f"z_{f}"].to_numpy(), 36), part.anomaly_return)["t_hac"])
                       for part in pieces for f in FEATURE_COLUMNS)
    assert shadows.max_abs_t_hac.iloc[0] == pytest.approx(expected_max)
    terciles, stability = describe_regimes(monthly)
    assert len(terciles) == 60 and len(stability) == 80
    assert terciles.groupby(["strategy", "feature"]).months.sum().eq(100).all()
    # Un retorno constante no fabrica significación ni una referencia nula igual a cero.
    monthly["anomaly_return"] = 0.0
    tests, shadows, report = screen_relationships(monthly)
    assert tests.p_holm.eq(1).all() and not tests.passes_holm.any()
    assert tests.exceeds_shadows.isna().all() and not report["shadow_comparison_available"]
    assert shadows.max_abs_t_hac.isna().all()


def test_notebook_continuous_response_persistence_and_invalidations(tmp_path, monkeypatch):
    pytest.importorskip("IPython")
    import matplotlib
    matplotlib.use("Agg")
    prices, industries, baa, aaa = feature_inputs()
    rng = np.random.default_rng(92)
    prices["price_monthly_mean"] = 100*np.exp(np.cumsum(rng.normal(.003, .03, len(prices))))
    for name in industries.columns[1:]:
        industries[name] = rng.normal(.003, .04, len(industries))
    baa["yield_percent"] += .2*np.sin(np.arange(len(baa))/11)
    aaa["yield_percent"] += .1*np.cos(np.arange(len(aaa))/13)
    sheet = workbook(monkeypatch)
    original_cell = sheet.cell
    values = prices.set_index("period").price_monthly_mean
    def cell(row, col):
        value = original_cell(row, col)
        if col == 1:
            value.value = float(values.loc[sheet.months[row - 8]])
        return value
    monkeypatch.setattr(sheet, "cell", cell)
    original = tmp_path / "original.xls"; original.write_bytes(XLS_SIGNATURE + b"synthetic")
    french = tmp_path / "original.zip"
    french.write_bytes(french_zip([f"{m.replace('-', '')},unused,unused,unused,0.20"
                       for m in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    prepare_shiller_data(tmp_path, file=original); calculate_signals(tmp_path)
    prepare_french_data(tmp_path, file=french); prepare_return_components(tmp_path)
    features = build_monthly_features(prices, industries, baa, aaa)
    save_result(tmp_path, "monthly_features", features, {"feature_columns": FEATURE_COLUMNS})
    components, _ = read_result(tmp_path, "monthly_return_components")
    signals, _ = read_result(tmp_path, "shiller_signals")
    labels = build_monthly_labels(components, signals, PARAMETERS).merge(features, on=["asset", "target_period", "decision_period"])
    labels["training_ready"] = labels.features_ready & labels.has_signal
    save_result(tmp_path, "labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})
    monkeypatch.setattr("tfm.data.project_root", lambda: tmp_path)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No descargar"))
    monkeypatch.setattr("tfm.sources.french.urlopen", lambda *a, **k: pytest.fail("No descargar"))
    notebook = json.loads((Path(__file__).parents[1] / "notebooks/09_cribado_regimen.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None and not cell["outputs"]
            exec(compile("".join(cell["source"]), "09_cribado_regimen.ipynb", "exec"), namespace)
    monthly = pd.read_parquet(tmp_path / "data/processed/screening_monthly.parquet")
    expected = simulate_baselines(components, signals, PARAMETERS)
    for rule in ("momentum", "reversal"):
        actual = monthly.loc[monthly.strategy.eq(rule)]
        source = expected.loc[expected.strategy.eq(rule)]
        assert actual.anomaly_return.tolist() == pytest.approx((source.net_return - source.rf_return).tolist())
    assert len(monthly) == 1512 and monthly.groupby("strategy").screening_ready.sum().eq(713).all()
    assert namespace["informe"]["first_target"] == "1930-08"
    assert len(namespace["contrastes"]) == 20 and len(namespace["sombras"]) == 642
    paths = [tmp_path / "data/processed" / f"{name}.{ext}" for name in RESULT_NAMES for ext in ("parquet", "json")]
    for name in RESULT_NAMES:
        path = tmp_path / "data/processed" / f"{name}.parquet"
        info = json.loads(path.with_suffix(".json").read_text())
        assert len(pd.read_parquet(path)) == info["rows"]
        assert info["family_size"] == 20 and info["scope"] == "descriptive_development_screening_only"
    before = {p: p.read_bytes() for p in paths}
    for regenerate in (calculate_signals, prepare_return_components, prepare_french_data, prepare_shiller_data):
        for p, content in before.items():p.write_bytes(content)
        regenerate(tmp_path)
        assert not any(p.exists() for p in paths)
    for name, table, report in (("monthly_features", features, {"feature_columns": FEATURE_COLUMNS}),
                               ("labelled_signals", labels, {"feature_columns": FEATURE_COLUMNS, "parameters": PARAMETERS})):
        for p, content in before.items():p.write_bytes(content)
        save_result(tmp_path, name, table, report)
        assert not any(p.exists() for p in paths)
