from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest

from tfm import cli
from tfm.preparation.calendar import audit_calendar
from test_backtesting import make_project


def prices(dates):
    return pd.DataFrame({"asset": ["SPY"] * len(dates), "observed_at": pd.to_datetime(dates), "adjusted_close": [100.0] * len(dates)})


def test_historical_closures_missing_edges_and_early_close():
    for start, end, sessions in [
        ("2001-09-10", "2001-09-18", ["2001-09-10", "2001-09-17"]),
        ("2012-10-26", "2012-11-01", ["2012-10-26", "2012-10-31"]),
        ("2018-12-04", "2018-12-07", ["2018-12-04", "2018-12-06"]),
    ]:
        result, _ = audit_calendar(prices(sessions), start, end, calendar_name="XNYS")
        assert result["status"] == "passed"
    result, schedule = audit_calendar(prices(["2020-12-24"]), "2020-12-24", "2020-12-25", calendar_name="XNYS")
    assert result["status"] == "passed"
    assert schedule["early_close"].tolist() == [True]
    result, _ = audit_calendar(prices(["2001-09-11", "2001-09-17"]), "2001-09-10", "2001-09-19", calendar_name="XNYS")
    assert result["missing_sessions"] == ["2001-09-10", "2001-09-18"]
    assert result["unexpected_sessions"] == ["2001-09-11"]


def project(tmp_path):
    simulation, prepared = make_project(tmp_path)
    config = tmp_path / "configs/audit.toml"
    config.write_bytes((Path(__file__).parents[1] / "configs/audit.toml").read_bytes())
    # La fixture financiera contiene un fin de descarga posterior al último dato;
    # aquí declaramos el intervalo auditado exacto, incluido 24/12 (sesión reducida).
    manifest = json.loads((prepared / "manifest.json").read_text())
    manifest["source_manifest"]["parameters"]["end"] = "2020-12-31"
    (prepared / "manifest.json").write_text(json.dumps(manifest))
    return config, simulation, prepared


def test_calendar_audit_cli_replay_and_explicit_simulation(tmp_path, monkeypatch, capsys):
    config, simulation, prepared = project(tmp_path)
    before = (prepared / "quality_report.json").read_bytes()
    args = ["audit-prices", "--config", str(config), "--prepared", str(prepared)]
    assert cli.main(args) == 0
    run = next((tmp_path / "outputs/runs").iterdir())
    report = json.loads((run / "audit_report.json").read_text())
    assert report["checks"]["calendar"]["expected_sessions"] == 4
    assert report["checks"]["prices"]["status"] == "not_evaluated"
    assert cli.main(args) == 0  # Nueva ejecución; originales intactos.
    assert (prepared / "quality_report.json").read_bytes() == before
    assert cli.main(["simulate-buy-and-hold", "--config", str(simulation), "--prepared", str(prepared), "--audit", str(run)]) == 0
    records = [(p.parent, json.loads(p.read_text())) for p in (tmp_path / "outputs/runs").glob("*/run.json")]
    sim_dir = next(p for p, r in records if r["command"] == "simulate-buy-and-hold")
    summary = json.loads((sim_dir / "summary.json").read_text())
    assert summary["checks"]["calendar"]["status"] == "passed"
    assert (sim_dir / "audit_report.json").read_bytes() == (run / "audit_report.json").read_bytes()
    assert all("calendario" not in w.lower() for w in summary["warnings"])
    assert cli.main(["simulate-buy-and-hold", "--config", str(simulation), "--prepared", str(prepared)]) == 0
    output = capsys.readouterr().out
    assert "Calendario: superado" in output
    assert "Contraste independiente de precios: pendiente" in output


@pytest.mark.parametrize("problem", ["different_data", "partial", "discrepancies"])
def test_incompatible_audit_cannot_accredit_simulation(tmp_path, problem):
    config, simulation, prepared = project(tmp_path)
    if problem == "discrepancies":
        # Extender por delante: falta una sesión en el extremo que no puede ocultarse.
        manifest = json.loads((prepared / "manifest.json").read_text())
        manifest["source_manifest"]["parameters"]["start"] = "2020-12-23"
        (prepared / "manifest.json").write_text(json.dumps(manifest))
    expected_exit = 1 if problem == "discrepancies" else 0
    assert cli.main(["audit-prices", "--config", str(config), "--prepared", str(prepared)]) == expected_exit
    run = next((tmp_path / "outputs/runs").iterdir())
    if problem == "different_data":
        manifest = json.loads((prepared / "manifest.json").read_text())
        manifest["preparation_id"] = "otra_preparacion"
        (prepared / "manifest.json").write_text(json.dumps(manifest))
    elif problem == "partial":
        report = json.loads((run / "audit_report.json").read_text())
        report["interval"]["start"] = "2020-12-28"
        data = json.dumps(report).encode()
        (run / "audit_report.json").write_bytes(data)
        record = json.loads((run / "run.json").read_text())
        record["artifacts_sha256"]["audit_report.json"] = sha256(data).hexdigest()
        (run / "run.json").write_text(json.dumps(record))
    else:
        record = json.loads((run / "run.json").read_text())
        assert record["status"] == "completed"
        assert record["audit_result"] == "failed"
    assert cli.main(["simulate-buy-and-hold", "--config", str(simulation), "--prepared", str(prepared), "--audit", str(run)]) == 1


@pytest.mark.parametrize("problem", ["reserved_interval", "integrity"])
def test_technical_audit_failure_has_no_published_result(tmp_path, problem):
    config, _, prepared = project(tmp_path)
    if problem == "reserved_interval":
        manifest = json.loads((prepared / "manifest.json").read_text())
        manifest["source_manifest"]["parameters"]["end"] = "2021-01-02"
        (prepared / "manifest.json").write_text(json.dumps(manifest))
    else:
        with (prepared / "prices.parquet").open("ab") as handle:
            handle.write(b"modified")
    assert cli.main(["audit-prices", "--config", str(config), "--prepared", str(prepared)]) == 1
    run = next((tmp_path / "outputs/runs").iterdir())
    assert json.loads((run / "run.json").read_text())["status"] == "failed"
    assert not (run / "audit_report.json").exists()
