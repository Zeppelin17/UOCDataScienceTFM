"""Selección temporal, calidad y descarga de Shiller; sin red ni datos reales."""

import json
import ssl
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import xlrd

from tfm.data import prepare_shiller_data
from tfm.preparation.shiller import COLUMNS, normalize_shiller
from tfm.sources.shiller import XLS_SIGNATURE


POLICY = (Path(__file__).parents[1] / "configs/estudio.toml").read_bytes()


class Sheet:
    ncols = 22

    def __init__(self, problem=None):
        self.months = ["1871-01", *pd.period_range("1925-12", "1989-12", freq="M").astype(str), "1990-01", "2026-10"]
        self.problem = problem
        if problem == "duplicate":
            self.months.insert(5, self.months[5])
        if problem == "missing":
            self.months.remove("1930-02")
        self.nrows = len(self.months) + 8

    def row_values(self, row, start, end):
        assert row == 7 and start == 0 and end == 3
        return ["Date", "P", "Wrong"] if self.problem == "header" else ["Date", "P", "D"]

    def cell_value(self, row, col):
        assert col == 0, "Solo se consultan fechas antes de filtrar la ventana"
        return float(self.months[row - 8].replace("-", "."))

    def cell(self, row, col):
        period = self.months[row - 8]
        assert "1925-12" <= period <= "1989-12", "Se han leído importes fuera del desarrollo/historia previa"
        assert col in (1, 2), "Se han leído columnas no autorizadas, incluidas rentabilidades futuras"
        value = 100.0 if col == 1 else 2.4
        if period == "1930-02":
            if self.problem == "non_finite":
                value = float("nan")
            elif self.problem == "negative":
                value = -1.0
        return SimpleNamespace(value=value, ctype=xlrd.XL_CELL_NUMBER)



def workbook(monkeypatch, problem=None):
    sheet = Sheet(problem)
    book = SimpleNamespace(sheet_by_name=lambda name: sheet, release_resources=lambda: None)
    monkeypatch.setattr("tfm.preparation.shiller.xlrd.open_workbook", lambda **kwargs: book)
    return sheet



def test_october_annualized_values_and_strict_column_temporal_selection(monkeypatch):
    workbook(monkeypatch)
    table, report = normalize_shiller(b"fixture", history_start="1925-12", policy_bytes=POLICY)
    assert table.columns.tolist() == COLUMNS
    assert table.period.iloc[10] == "1926-10"
    assert table.dividend_annualized.eq(2.4).all()  # No dividir por 12 ni convertir en pago mensual.
    assert report["rows"] == 769 and report["history_rows"] == 13 and report["development_rows"] == 756
    assert table.period.iloc[-1] == "1989-12" and report["status"] == "passed"



def project(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    config = configs / "estudio.toml"
    config.write_bytes(POLICY)
    original = tmp_path / "original.xls"
    original.write_bytes(XLS_SIGNATURE + b"synthetic workbook; reader provided by test")
    return config, original


@pytest.mark.parametrize("problem", ["duplicate", "missing", "non_finite", "negative"])
def test_bad_quality_blocks_publication(tmp_path, monkeypatch, problem):
    workbook(monkeypatch, problem)
    config, original = project(tmp_path)
    before = original.read_bytes()
    with pytest.raises(ValueError, match="No se han preparado los datos"):
        prepare_shiller_data(config, file=original)
    assert not (tmp_path / "data/processed/shiller_monthly.parquet").exists()
    assert original.read_bytes() == before


@pytest.mark.parametrize("problem", ["policy", "header"])
def test_invalid_policy_and_source_header_are_rejected(tmp_path, monkeypatch, problem):
    workbook(monkeypatch, "header" if problem == "header" else None)
    config, original = project(tmp_path)
    if problem == "policy":
        config.write_text(config.read_text().replace("1989-12-31", "1990-12-31"))
    with pytest.raises(ValueError):
        prepare_shiller_data(config, file=original)
    assert not (tmp_path / "data/processed/shiller_monthly.parquet").exists()


def test_download_preserves_exact_bytes_and_source_with_verified_https(tmp_path, monkeypatch):
    workbook(monkeypatch)
    config, original = project(tmp_path)
    response = SimpleNamespace(geturl=lambda: "https://www.econ.yale.edu/~shiller/data/ie_data.xls",
                               read=lambda size: original.read_bytes())
    class Response:
        def __enter__(self):
            return response
        def __exit__(self, *args):
            return False
    def download(request, **kwargs):
        assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["context"].check_hostname is True
        return Response()
    monkeypatch.setattr("tfm.sources.shiller.urlopen", download)
    prepare_shiller_data(config)
    assert (tmp_path / "data/raw/shiller.xls").read_bytes() == original.read_bytes()
    source = json.loads((tmp_path / "data/raw/shiller_fuente.json").read_bytes())
    assert source["acquisition"]["method"] == "https_download"
    assert source["acquisition"]["resolved_url"] == response.geturl()
