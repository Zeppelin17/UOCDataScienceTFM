from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from openpyxl import Workbook
import pandas as pd
import pytest

from tfm import cli
from tfm.pipeline import import_ssga_reference, run_audit_prices, run_buy_and_hold, PipelineError
from tfm.preparation.reconciliation import ABSOLUTE_TOLERANCE_USD, reconcile_dividends
from tfm.sources.ssga import HEADERS, parse_distributions
from test_calendar_audit import project


def excel(path):
    book = Workbook()
    sheet = book.active
    sheet.title = "dividend"
    sheet.append(HEADERS)
    for when, amount, gain in [("03/19/1993", "0.213191", None), ("12/28/2020", "0.500400", None),
                                ("01/04/2021", "DO_NOT_PARSE_HOLDOUT", "ALSO_NOT_PARSED")]:
        sheet.append(["SPY fund", "SPY", "78462F103", when, None, None, amount, gain, None, "Quarterly"])
    book.save(path)
    return path


def setup(tmp_path):
    _, simulation, prepared = project(tmp_path)
    root = Path(__file__).parents[1]
    config = tmp_path / "configs/reconciliation.toml"
    config.write_text((root / "configs/reconciliation.toml").read_text()
                      .replace('start = "1993-01-29"', 'start = "2020-12-24"')
                      .replace('end = "2021-01-01"', 'end = "2020-12-31"'))
    frame = pd.read_parquet(prepared / "prices.parquet")
    frame.loc[frame.observed_at.eq(pd.Timestamp("2020-12-28")), "dividends"] = 0.5
    frame.to_parquet(prepared / "prices.parquet", index=False)
    manifest = json.loads((prepared / "manifest.json").read_text())
    manifest["sha256"] = sha256((prepared / "prices.parquet").read_bytes()).hexdigest()
    (prepared / "manifest.json").write_text(json.dumps(manifest))
    reference = import_ssga_reference(config, excel(tmp_path / "official.xlsx"))
    return config, simulation, prepared, reference


def test_official_adapter_preserves_original_and_excludes_holdout_amounts(tmp_path):
    config, _, _, reference = setup(tmp_path)
    assert (reference / "original.xlsx").read_bytes() == (tmp_path / "official.xlsx").read_bytes()
    normalized = pd.read_parquet(reference / "dividends.parquet")
    assert normalized.observed_at.dt.strftime("%Y-%m-%d").tolist() == ["2020-12-28"]
    assert normalized.cash_distribution.tolist() == [0.5004]
    assert (reference / "config.toml").read_bytes() == config.read_bytes()
    # Una fuente ajena o un formato modificado no debe normalizarse silenciosamente.
    book = Workbook(); book.active.title = "dividend"; book.active.append(["Unexpected"])
    data = BytesIO(); book.save(data)
    with pytest.raises(ValueError, match="Cabecera"):
        parse_distributions(data.getvalue(), "1993-01-29", "2021-01-01")


def test_all_events_are_compared_coverage_does_not_hide_discrepancies():
    prices = pd.DataFrame({"observed_at": pd.to_datetime(["2020-12-28", "2020-12-29", "2020-12-30"]),
                           "dividends": [0.5, 0, 0.25], "stock_splits": [0, 0, 0]})
    ref = pd.DataFrame({"observed_at": pd.to_datetime(["2020-12-28", "2020-12-29"]),
                        "cash_distribution": [0.5004, 0.75], "income_dividend": [0.5004, 0.75],
                        "short_term_gain": [0, 0], "long_term_gain": [0, 0]})
    coverage = {"start": "2020-12-28", "end_exclusive": "2020-12-31"}
    check, details = reconcile_dividends(prices, ref, coverage, "2020-12-24", "2020-12-31", tolerance=ABSOLUTE_TOLERANCE_USD)
    assert check["coverage"] == "partial" and check["agreement"] == "discrepant" and check["status"] == "failed"
    assert details.result.tolist() == ["within_tolerance", "missing_in_yahoo", "missing_in_reference"]
    check, _ = reconcile_dividends(prices.iloc[:1], ref.iloc[:1], coverage, "2020-12-24", "2020-12-31", tolerance=ABSOLUTE_TOLERANCE_USD)
    assert check["coverage"] == "partial" and check["status"] == "partial"
    ref.loc[0, "cash_distribution"] = 0.501
    check, _ = reconcile_dividends(prices.iloc[:1], ref.iloc[:1], coverage, "2020-12-28", "2020-12-31", tolerance=ABSOLUTE_TOLERANCE_USD)
    assert check["status"] == "failed" and check["coverage"] == "complete"


def test_cli_replay_and_simulation_keep_checks_separate(tmp_path, monkeypatch, capsys):
    config, simulation, prepared, reference = setup(tmp_path)
    original = (prepared / "prices.parquet").read_bytes()
    args = ["audit-prices", "--config", str(config), "--prepared", str(prepared), "--reference", str(reference)]
    assert cli.main(args) == 0
    run = next((tmp_path / "outputs/runs").iterdir())
    report = json.loads((run / "audit_report.json").read_bytes())
    assert report["checks"]["dividends"]["status"] == "passed"
    assert report["checks"]["prices"]["status"] == "not_evaluated"
    assert json.loads((run / "run.json").read_bytes())["audit_result"] == "partial"
    assert cli.main(["simulate-buy-and-hold", "--config", str(simulation), "--prepared", str(prepared), "--audit", str(run)]) == 0
    assert cli.main(args) == 0
    assert (prepared / "prices.parquet").read_bytes() == original
    output = capsys.readouterr().out
    assert "cobertura completa; concordancia dentro de tolerancia" in output
    assert "Contraste independiente de precios: pendiente" in output


@pytest.mark.parametrize("problem", ["original", "comparison", "claim"])
def test_altered_reference_or_report_cannot_accredit_simulation(tmp_path, problem):
    config, simulation, prepared, reference = setup(tmp_path)
    run = run_audit_prices(config, prepared, reference)
    if problem == "original":
        with (reference / "original.xlsx").open("ab") as handle:
            handle.write(b"changed")
    elif problem == "comparison":
        details = pd.read_parquet(run / "distribution_comparison.parquet")
        details.loc[0, "ssga_distribution"] = 9.0
        details.to_parquet(run / "distribution_comparison.parquet", index=False)
        record = json.loads((run / "run.json").read_bytes())
        record["artifacts_sha256"]["distribution_comparison.parquet"] = sha256((run / "distribution_comparison.parquet").read_bytes()).hexdigest()
        (run / "run.json").write_text(json.dumps(record))
    else:
        report = json.loads((run / "audit_report.json").read_bytes())
        report["checks"]["prices"]["status"] = "passed"
        (run / "audit_report.json").write_text(json.dumps(report))
        record = json.loads((run / "run.json").read_bytes())
        record["artifacts_sha256"]["audit_report.json"] = sha256((run / "audit_report.json").read_bytes()).hexdigest()
        (run / "run.json").write_text(json.dumps(record))
    with pytest.raises(PipelineError):
        run_buy_and_hold(simulation, prepared, run)


def test_discrepancy_is_completed_but_blocks_attaching_audit(tmp_path):
    config, simulation, prepared, reference = setup(tmp_path)
    frame = pd.read_parquet(prepared / "prices.parquet")
    frame.loc[frame.dividends.gt(0), "dividends"] = 0.75
    frame.to_parquet(prepared / "prices.parquet", index=False)
    manifest = json.loads((prepared / "manifest.json").read_bytes())
    manifest["sha256"] = sha256((prepared / "prices.parquet").read_bytes()).hexdigest()
    (prepared / "manifest.json").write_text(json.dumps(manifest))
    assert cli.main(["audit-prices", "--config", str(config), "--prepared", str(prepared), "--reference", str(reference)]) == 1
    run = next((tmp_path / "outputs/runs").iterdir())
    record = json.loads((run / "run.json").read_bytes())
    assert record["status"] == "completed" and record["audit_result"] == "failed"
    with pytest.raises(PipelineError, match="discrepancias"):
        run_buy_and_hold(simulation, prepared, run)


def test_reserved_reference_window_rejected_before_archive(tmp_path):
    config, _, _, _ = setup(tmp_path)
    config.write_text(config.read_text().replace('end = "2020-12-31"', 'end = "2021-01-05"'))
    with pytest.raises(ValueError, match="reservado"):
        import_ssga_reference(config, tmp_path / "official.xlsx")
    assert len(list((tmp_path / "data/raw/ssga/SPY").iterdir())) == 1
