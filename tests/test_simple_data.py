"""Regresiones del flujo simplificado: mismas tablas, sin runs ni huellas."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tfm.data import calculate_signals, load_monthly, prepare_shiller_data
from tfm.preparation.shiller import normalize_shiller
from tfm.signals.shiller import build_price_signals
from tfm.sources.shiller import XLS_SIGNATURE
from test_shiller import workbook


@pytest.fixture
def study(tmp_path, monkeypatch):
    original = tmp_path / "original.xls"
    original.write_bytes(XLS_SIGNATURE + b"synthetic workbook")
    workbook(monkeypatch)
    monkeypatch.setattr("tfm.sources.shiller.urlopen", lambda *a, **k: pytest.fail("No debe descargar"))
    return tmp_path, original


def test_offline_preparation_has_identical_data_signals_and_stable_paths(study, capsys):
    root, original = study
    prepare_shiller_data(root, file=original)
    calculate_signals(root)
    expected, _ = normalize_shiller(original.read_bytes(), history_start="1924-12")
    pd.testing.assert_frame_equal(load_monthly(root), expected)
    result = pd.read_parquet(root / "data/processed/shiller_signals.parquet")
    expected_signals = build_price_signals(expected)
    expected_signals = expected_signals.loc[expected_signals.target_period.between("1927-01", "1989-12")].reset_index(drop=True)
    pd.testing.assert_frame_equal(result, expected_signals)
    assert len(expected) == 781 and len(result) == 756 and result.both_rules_available.sum() == 756
    assert result.loc[0, "target_period"] == "1927-01"
    assert result.loc[0, "both_rules_available"]
    assert (root / "data/raw/shiller.xls").read_bytes() == original.read_bytes()
    source = json.loads((root / "data/raw/shiller_fuente.json").read_bytes())
    assert source["acquisition"]["method"] == "local_file_import"
    assert "sha256" not in source and not (root / "outputs").exists()
    assert not list((root / "data").rglob("*.csv"))
    files = {p.relative_to(root) for p in (root / "data").rglob("*") if p.is_file()}
    calculate_signals(root)
    assert files == {p.relative_to(root) for p in (root / "data").rglob("*") if p.is_file()}
    # La nueva tabla de variables depende también de los precios preparados.
    features = root / "data/processed/monthly_features.parquet"
    features.write_bytes(b"previous features")
    features.with_suffix(".json").write_text("{}")
    prepare_shiller_data(root)  # Reutiliza sin contactar con la fuente.
    assert not features.exists() and not features.with_suffix(".json").exists()
    assert not (root / "data/processed/shiller_signals.parquet").exists()
    assert not (root / "data/processed/shiller_signals.json").exists()


def test_bad_input_and_failed_write_keep_previous_valid_outputs(study, monkeypatch):
    root, original = study
    prepare_shiller_data(root, file=original)
    calculate_signals(root)
    before = {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}
    workbook(monkeypatch, "duplicate")
    with pytest.raises(ValueError, match="duplicate_months"):
        prepare_shiller_data(root)
    workbook(monkeypatch)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda *a, **k: (_ for _ in ()).throw(OSError("disco lleno")))
    with pytest.raises(OSError, match="disco lleno"):
        prepare_shiller_data(root)
    assert before == {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}


def test_original_replacement_is_explicit(study):
    root, original = study
    prepare_shiller_data(root, file=original)
    with pytest.raises(ValueError, match="Ya existe el original"):
        prepare_shiller_data(root, file=original)


@pytest.mark.parametrize("failure", ["table", "summary", "dependent"])
def test_publication_failure_restores_data_summary_and_signals(study, monkeypatch, failure):
    root, original = study
    prepare_shiller_data(root, file=original)
    calculate_signals(root)
    before = {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}
    # La nueva lectura daría otros precios y otro resumen: no basta con dejar
    # los archivos recién escritos para que la comparación por bytes pase.
    sheet = workbook(monkeypatch)
    sheet.months.append("2027-01")
    sheet.nrows += 1
    cell = sheet.cell
    def revised_cell(row, column):
        result = cell(row, column)
        if column == 1:
            result.value *= 2
        return result
    monkeypatch.setattr(sheet, "cell", revised_cell)
    replace, unlink = Path.replace, Path.unlink
    failing_name = "shiller_monthly.parquet.tmp" if failure == "table" else "shiller_monthly.json.tmp"
    def fail_replace(path, target):
        if failure != "dependent" and path.name == failing_name:
            raise PermissionError("archivo bloqueado")
        return replace(path, target)
    def fail_unlink(path, *args, **kwargs):
        if failure == "dependent" and path.name == "shiller_signals.json":
            raise PermissionError("archivo bloqueado")
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(PermissionError, match="archivo bloqueado"):
        prepare_shiller_data(root)
    assert before == {p: p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}
    assert len(load_monthly(root)) == 781
