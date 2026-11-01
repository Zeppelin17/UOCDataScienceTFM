"""Controles esenciales del diagnóstico, con fuentes sintéticas y sin red."""

from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from tfm.diagnostics import (INDUSTRIES, compare_price_definitions, coverage_table, feature_availability,
                             load_context_sources, load_diagnostic_sources, parse_fred_yield, parse_industry_returns, yahoo_monthly)
from tfm.sources.shiller import XLS_SIGNATURE
from test_shiller import workbook


def industries_zip(*, missing=False):
    rows = ["Average Value Weighted Returns -- Monthly", "," + ",".join(INDUSTRIES)]
    for month in pd.period_range("1926-07", "1989-12", freq="M"):
        values = ["1.00"] * 12
        if missing and str(month) == "1930-02":
            values[0] = "-99.99"
        rows.append(str(month).replace("-", "") + "," + ",".join(values))
    rows.extend(["199001," + ",".join(["future-not-read"] * 12), "", "Average Equal Weighted Returns -- Monthly",
                 "," + ",".join(INDUSTRIES), "192607," + ",".join(["99"] * 12)])
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("12_Industry_Portfolios.csv", "\n".join(rows))
    return content.getvalue()


def fred_csv(series, *, missing=False):
    rows = ["observation_date," + series]
    for month in pd.period_range("1919-01", "1989-12", freq="M"):
        if missing and str(month) == "1930-02":
            continue
        rows.append(f"{month}-01,5.35")
    rows.append("1990-01-01,future-not-read")
    return "\n".join(rows).encode()


def test_original_units_selected_block_missing_values_and_no_future_amounts():
    industries = parse_industry_returns(industries_zip())
    assert len(industries) == 762 and industries.period.iloc[0] == "1926-07"
    assert industries.NoDur.eq(0.01).all()  # Primer bloque ponderado por valor, no el de pesos iguales.
    fred = parse_fred_yield(fred_csv("BAA"), "BAA")
    assert len(fred) == 852 and fred.yield_percent.eq(5.35).all()  # Tipo anual en %, no retorno RF mensual.
    assert fred.period.iloc[-1] == industries.period.iloc[-1] == "1989-12"
    with pytest.raises(ValueError, match="ausentes"):
        parse_industry_returns(industries_zip(missing=True))
    with pytest.raises(ValueError, match="meses ausentes"):
        parse_fred_yield(fred_csv("BAA", missing=True), "BAA")
    with pytest.raises(ValueError, match="incompatible"):
        parse_fred_yield(fred_csv("AAA"), "BAA")


def test_monthly_definitions_common_signal_dates_and_price_only_payoffs():
    daily = pd.DataFrame({"Close": [5.0, 10.0, 20.0, 30.0, 50.0]},
                         index=pd.to_datetime(["1989-10-31", "1989-11-01", "1989-11-30", "1989-12-01", "1989-12-29"]))
    monthly = yahoo_monthly(daily)
    assert monthly.yahoo_mean.tolist() == [5.0, 15.0, 40.0]
    assert monthly.yahoo_close.tolist() == [5.0, 20.0, 50.0]
    assert monthly.mean_usable.tolist() == [False, True, True]
    periods = pd.period_range("1986-12", "1989-12", freq="M").astype(str)
    prices = [100 * 1.01**i for i in range(len(periods))]
    shiller = pd.DataFrame({"period": periods, "price_monthly_mean": prices})
    yahoo = pd.DataFrame({"period": periods, "yahoo_mean": [2 * value for value in prices],
                          "yahoo_close": [value * (1.1 if i % 2 else 0.9) for i, value in enumerate(prices)],
                          "mean_usable": [False, *([True] * (len(periods) - 1))]})
    result = compare_price_definitions(shiller, yahoo)
    assert result["statistics"].months.eq(23).all()
    assert result["signals"].target_period.min() == "1988-02"
    assert result["signals"].target_period.max() == "1989-12"
    equal = result["agreement"].query("left == 'shiller_mean' and right == 'yahoo_mean'")
    assert equal.different_signals.eq(0).all()
    stats = result["statistics"].set_index("basis").loc["shiller_mean"]
    assert stats.momentum_mean_gross_price_payoff == pytest.approx(0.01)
    assert stats.reversal_mean_gross_price_payoff == pytest.approx(-0.01)
    assert (result["agreement"].different_signals > 0).any()
    changed = yahoo.copy(); changed.loc[len(changed)] = ["1990-01", 10000, 1, True]
    future_shiller = pd.concat([shiller, pd.DataFrame({"period": ["1990-01"], "price_monthly_mean": [9999]})])
    again = compare_price_definitions(future_shiller, changed)
    for name in result:
        pd.testing.assert_frame_equal(result[name], again[name])


def test_cached_sources_preserved_and_initial_availability_is_explicit(tmp_path, monkeypatch):
    workbook(monkeypatch)
    raw = tmp_path / "data/raw"; folder = raw / "diagnosis"; folder.mkdir(parents=True)
    (raw / "shiller.xls").write_bytes(XLS_SIGNATURE + b"synthetic")
    (folder / "12_industries.zip").write_bytes(industries_zip())
    for name in ("BAA", "AAA"):
        (folder / f"{name.lower()}.csv").write_bytes(fred_csv(name))
    dates = pd.date_range("1927-12-01", "1989-12-31", freq="BME")
    pd.DataFrame({"Close": 100.0}, index=dates).to_parquet(folder / "gspc_daily_1920_1989.parquet")
    before = {p: p.read_bytes() for p in raw.rglob("*") if p.is_file()}
    monkeypatch.setattr("tfm.diagnostics.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    monkeypatch.setattr("tfm.diagnostics.fetch_prices", lambda *a, **k: pytest.fail("No debe descargar"))
    context = load_context_sources(tmp_path)
    assert set(context) == {"industries", "BAA", "AAA"}
    sources = load_diagnostic_sources(tmp_path)
    assert before == {p: p.read_bytes() for p in raw.rglob("*") if p.is_file()}
    coverage = coverage_table(sources).set_index("source")
    assert coverage.loc["yahoo", "missing_development_months"] == 11
    assert coverage.loc["shiller", "development_months"] == 756
    availability = feature_availability(sources).set_index("feature")
    breadth = availability.loc["Amplitud industrial sobre media de 12 meses"]
    assert breadth.first_available_target == "1927-08" and breadth.development_months == 749
    assert availability.loc["Diferencial Baa–Aaa", "development_months"] == 756
    assert not (tmp_path / "configs").exists() and not (tmp_path / "data/processed").exists()
