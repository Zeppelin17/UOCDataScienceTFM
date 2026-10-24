"""Unidades RF, cálculo manual, alineación y recorrido nuevo sin red."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from tfm import cli, menu
from tfm.config import load_config
from tfm.data import prepare_shiller_data, prepare_french_data, prepare_return_components, read_result
from tfm.preparation.french import normalize_french_rf
from tfm.returns import build_return_components
from tfm.sources.french import SOURCE_URL, fetch_french
from tfm.sources.shiller import INSTRUMENT, XLS_SIGNATURE
from test_shiller import workbook


def french_zip(rows):
    stream = BytesIO()
    text = "Monthly file\n\n,Mkt-RF,SMB,HML,RF\n" + "\n".join(rows)
    text += "\n\n Annual Factors: January-December\n1927,0,0,0,999\n"
    with ZipFile(stream, "w") as archive:
        archive.writestr("F-F_Research_Data_Factors.csv", text)
    return stream.getvalue()


def test_rf_units_negative_values_and_exclusion_of_other_fields_and_future():
    content = french_zip(["192612,do not parse,do not parse,do not parse,not selected",
                          "192701,unused,unused,unused,0.20", "192702,unused,unused,unused,-0.05",
                          "199001,unused,unused,unused,future must not be converted"])
    table, report = normalize_french_rf(content, start="1927-01", end="1927-02")
    assert table.period.tolist() == ["1927-01", "1927-02"]
    assert table.rf_return.tolist() == pytest.approx([0.002, -0.0005])
    assert report["output_unit"] == "decimal_monthly_return"
    for bad_rows in (["192701,0,0,0,0.2"],  # No rellenar el mes ausente.
                     ["192701,0,0,0,0.2", "192701,0,0,0,0.2", "192702,0,0,0,0.2"],
                     ["192701,0,0,0,-99.99", "192702,0,0,0,0.2"]):
        with pytest.raises(ValueError):
            normalize_french_rf(french_zip(bad_rows), start="1927-01", end="1927-02")


def test_manual_return_components_and_missing_alignment():
    monthly = pd.DataFrame({"asset": INSTRUMENT, "period": ["1926-12", "1927-01", "1927-02"],
                            "price_monthly_mean": [100.0, 110.0, 99.0],
                            "dividend_annualized": [12.0, 12.0, 13.2]})
    rf = pd.DataFrame({"period": ["1927-01", "1927-02"], "rf_return": [0.002, -0.0005]})
    result = build_return_components(monthly, rf, start="1927-01", end="1927-02")
    assert result.previous_period.tolist() == ["1926-12", "1927-01"]
    assert result.price_return.tolist() == pytest.approx([0.10, -0.10])
    assert result.dividend_monthly_approx.tolist() == pytest.approx([1, 1.1])
    assert result.dividend_return_approx.tolist() == pytest.approx([0.01, 0.01])
    assert result.total_return_approx.tolist() == pytest.approx([0.11, -0.09])
    assert result.rf_return.tolist() == pytest.approx([0.002, -0.0005])
    with pytest.raises(ValueError, match="meses"):
        build_return_components(monthly, rf.iloc[:1], start="1927-01", end="1927-02")
    with pytest.raises(ValueError, match="mes anterior"):
        build_return_components(monthly.iloc[1:], rf, start="1927-01", end="1927-02")
    # Un mes posterior no cambia los componentes ya calculados.
    future = pd.DataFrame({"asset": [INSTRUMENT], "period": ["1990-01"],
                           "price_monthly_mean": [float("nan")], "dividend_annualized": [float("nan")]})
    pd.testing.assert_frame_equal(result, build_return_components(pd.concat([monthly, future]), rf,
                                                                start="1927-01", end="1927-02"))


def test_french_https_checks_and_local_import(tmp_path, monkeypatch):
    content = french_zip(["192701,0,0,0,0.20"])
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return SOURCE_URL
        def read(self, size): return content
    def download(request, **kwargs):
        assert kwargs["context"].check_hostname
        return Response()
    monkeypatch.setattr("tfm.sources.french.urlopen", download)
    assert fetch_french(url=SOURCE_URL)[0] == content
    monkeypatch.setattr(Response, "geturl", lambda self: "https://example.com/unexpected.zip")
    with pytest.raises(ValueError, match="Kenneth French"):
        fetch_french(url=SOURCE_URL)
    original = tmp_path / "original.zip"
    original.write_bytes(content)
    monkeypatch.setattr("tfm.sources.french.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    assert fetch_french(url=SOURCE_URL, file=original)[0] == content


def test_offline_cli_menu_and_dependency_invalidation(tmp_path, monkeypatch, capsys):
    configs = tmp_path / "configs"
    configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/estudio.toml").read_bytes())
    workbook(monkeypatch)
    shiller = tmp_path / "original.xls"
    shiller.write_bytes(XLS_SIGNATURE + b"synthetic workbook")
    prepare_shiller_data(config, file=shiller)
    original = tmp_path / "french.zip"
    original.write_bytes(french_zip([f"{month.replace('-', '')},unused,unused,unused,0.20"
                                    for month in pd.period_range("1927-01", "1989-12", freq="M").astype(str)]))
    monkeypatch.setattr("tfm.sources.french.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    assert cli.main(["prepare-data", "--source", "french", "--config", str(config), "--file", str(original)]) == 0
    assert cli.main(["prepare-returns", "--config", str(config)]) == 0
    table, report = read_result(load_config(config), "monthly_return_components")
    assert len(table) == 756 and report["last_period"] == "1989-12"
    assert table.price_return.eq(0).all()
    assert table.dividend_return_approx.eq(0.002).all()
    assert table.rf_return.eq(0.002).all()
    assert not (tmp_path / "outputs").exists()
    before = {p: p.read_bytes() for p in (tmp_path / "data").rglob("*") if p.is_file()}
    answers = iter(["6", "", "7", "", "3", "5", "", "0", "0"])
    monkeypatch.setattr(menu, "_clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert menu.interactive_menu(config) == 0
    assert "Todavía no se han aplicado señales, posiciones ni costes" in capsys.readouterr().out
    assert (tmp_path / "data/raw/french_factors.zip").read_bytes() == original.read_bytes()
    # Volver a preparar French retira los componentes, pero conserva Shiller.
    prepare_french_data(config)
    path = tmp_path / "data/processed/monthly_return_components.parquet"
    assert not path.exists()
    with pytest.raises(ValueError, match="Faltan componentes"):
        read_result(load_config(config), "monthly_return_components")
    assert (tmp_path / "data/processed/shiller_monthly.parquet").read_bytes() == before[tmp_path / "data/processed/shiller_monthly.parquet"]
    prepare_return_components(config)
    # Una entrada inválida no destruye el resultado anterior.
    good = path.read_bytes()
    monkeypatch.setattr("tfm.data.build_return_components", lambda *a, **k: (_ for _ in ()).throw(ValueError("entrada inválida")))
    with pytest.raises(ValueError, match="entrada inválida"):
        prepare_return_components(config)
    assert path.read_bytes() == good
    prepare_shiller_data(config)
    assert not path.exists() and not path.with_suffix(".json").exists()
