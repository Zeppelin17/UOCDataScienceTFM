"""Regresiones del contrato temporal y recorrido mensual; sin red ni datos del emisor."""

from hashlib import sha256
import json
import ssl
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import xlrd

from tfm import cli
from tfm.pipeline import run_prepare_shiller, PipelineError
from tfm.preparation.shiller import COLUMNS, load_shiller_monthly, normalize_shiller
from tfm.sources.shiller import XLS_SIGNATURE


POLICY = (Path(__file__).parents[1] / "configs/historical_policy.toml").read_bytes()


class Sheet:
    ncols = 22

    def __init__(self, problem=None):
        self.months = ["1871-01", *pd.period_range("1926-01", "1989-12", freq="M").astype(str), "1990-01", "2026-10"]
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
        assert "1926-01" <= period <= "1989-12", "Se han leído importes fuera del desarrollo/historia previa"
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


def project(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    for name in ("shiller_monthly.toml", "historical_policy.toml", "data.toml"):
        (configs / name).write_bytes((Path(__file__).parents[1] / "configs" / name).read_bytes())
    original = tmp_path / "original.xls"
    original.write_bytes(XLS_SIGNATURE + b"synthetic workbook; reader provided by test")
    return configs / "shiller_monthly.toml", original


def test_october_annualized_values_and_strict_column_temporal_selection(monkeypatch):
    workbook(monkeypatch)
    table, report = normalize_shiller(b"fixture", history_start="1926-01", policy_bytes=POLICY)
    assert table.columns.tolist() == COLUMNS
    assert table.period.iloc[9] == "1926-10"
    assert table.dividend_annualized.eq(2.4).all()  # No dividir por 12 ni convertir en pago mensual.
    assert report["rows"] == 768 and report["history_rows"] == 12 and report["development_rows"] == 756
    assert table.period.iloc[-1] == "1989-12" and report["status"] == "passed"


@pytest.mark.parametrize("problem", ["duplicate", "missing", "non_finite", "negative"])
def test_bad_quality_records_failure_without_publishing_table(tmp_path, monkeypatch, problem):
    workbook(monkeypatch, problem)
    config, original = project(tmp_path)
    with pytest.raises(PipelineError) as error:
        run_prepare_shiller(config, file_path=original)
    record = json.loads((error.value.run_dir / "run.json").read_bytes())
    assert record["status"] == "failed" and record["stage"] == "preparation"
    report = Path(record["quality_report_path"])
    assert json.loads(report.read_bytes())["status"] == "failed"
    assert not (report.parent / "monthly.parquet").exists()
    assert (Path(record["snapshot_dir"]) / "original.xls").read_bytes() == original.read_bytes()


def test_import_offline_replay_and_prepared_integrity(tmp_path, monkeypatch, capsys):
    workbook(monkeypatch)
    config, original = project(tmp_path)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *args, **kwargs: pytest.fail("No debe acceder a la red"))
    assert cli.main(["prepare-shiller", "--config", str(config), "--file", str(original)]) == 0
    run = next((tmp_path / "outputs/runs").iterdir())
    record = json.loads((run / "run.json").read_bytes())
    prepared, snapshot = Path(record["prepared_dir"]), Path(record["snapshot_dir"])
    before = original.read_bytes()
    table, _, _ = load_shiller_monthly(prepared, POLICY)
    assert (snapshot / "original.xls").read_bytes() == before
    assert (run / "validation_policy.toml").read_bytes() == POLICY
    assert cli.main(["prepare-shiller", "--config", str(config), "--snapshot", str(snapshot)]) == 0
    for path in (tmp_path / "outputs/runs").glob("*/run.json"):
        result = json.loads(path.read_bytes())
        pd.testing.assert_frame_equal(table, pd.read_parquet(Path(result["prepared_dir"]) / "monthly.parquet"))
    output = capsys.readouterr().out
    assert "756 meses" in output and "precio de orden" in output
    assert "importes excluidos" in output
    assert original.read_bytes() == before
    with (prepared / "monthly.parquet").open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        load_shiller_monthly(prepared, POLICY)


@pytest.mark.parametrize("problem", ["policy", "snapshot", "header"])
def test_policy_integrity_and_schema_errors_fail_explicitly(tmp_path, monkeypatch, problem):
    workbook(monkeypatch)
    config, original = project(tmp_path)
    run = run_prepare_shiller(config, file_path=original)
    record = json.loads((run / "run.json").read_bytes())
    snapshot = Path(record["snapshot_dir"])
    if problem == "policy":
        policy = tmp_path / "configs/historical_policy.toml"
        policy.write_text(policy.read_text().replace('1989-12-31', '1990-12-31').replace('1990-01-01', '1991-01-01'))
    elif problem == "snapshot":
        with (snapshot / "original.xls").open("ab") as handle:
            handle.write(b"changed")
    else:
        workbook(monkeypatch, "header")
    with pytest.raises(PipelineError) as error:
        run_prepare_shiller(config, snapshot_dir=snapshot)
    result = json.loads((error.value.run_dir / "run.json").read_bytes())
    assert result["status"] == "failed" and result["prepared_dir"] is None
    assert not (error.value.run_dir / "prepared_manifest.json").exists()
    assert len(list((tmp_path / "data/processed/shiller_monthly").iterdir())) == 1


def test_download_archives_the_exact_response_and_provenance(tmp_path, monkeypatch):
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
    run = run_prepare_shiller(config)
    record = json.loads((run / "run.json").read_bytes())
    snapshot = Path(record["snapshot_dir"])
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    assert manifest["acquisition"]["method"] == "https_download"
    assert manifest["sha256"] == sha256(original.read_bytes()).hexdigest()
    assert manifest["status"] == "archived"
