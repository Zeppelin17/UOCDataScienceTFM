"""Pruebas esenciales de señales, procedencia y bloqueo temporal; sin red."""

from hashlib import sha256
import json
from pathlib import Path
import socket

import pandas as pd
import pytest

from tfm import cli
from tfm.pipeline import PipelineError, run_shiller_signals
from tfm.signals.shiller import build_price_signals
from tfm.sources.shiller import INSTRUMENT


def test_fixed_windows_directions_and_no_future_dependency():
    table = pd.DataFrame({
        "asset": INSTRUMENT,
        "period": pd.period_range("1926-01", periods=14, freq="M").astype(str),
        "price_monthly_mean": [100, *([110] * 10), 50, 130, 130],
        "dividend_annualized": [object() for _ in range(14)],  # No debe consultarse.
    })
    result = build_price_signals(table)
    assert pd.isna(result.loc[11, "momentum_signal"])
    assert result.loc[12, "momentum_score"] == pytest.approx(-0.5)
    assert result.loc[12, "momentum_signal"] == 0
    assert result.loc[12, "reversal_signal"] == -1
    assert result.loc[11, "reversal_signal"] == 1
    assert result.loc[13, "momentum_signal"] == 1
    assert result.loc[13, "reversal_signal"] == 0
    assert result.loc[12, "decision_period"] == "1927-01"
    assert result.loc[12, "target_period"] == "1927-02"
    pd.testing.assert_frame_equal(build_price_signals(table.iloc[:13]), result.iloc[:13])
    changed = table.copy()
    changed.loc[13, "price_monthly_mean"] = 1
    pd.testing.assert_frame_equal(build_price_signals(changed).iloc[:13], result.iloc[:13])
    changed.loc[12, "price_monthly_mean"] = 300
    assert build_price_signals(changed).loc[12, "momentum_score"] == result.loc[12, "momentum_score"]


@pytest.fixture
def prepared_project(tmp_path):
    root = Path(__file__).parents[1]
    configs = tmp_path / "configs"
    configs.mkdir()
    for name in ("shiller_signals.toml", "historical_policy.toml", "data.toml"):
        (configs / name).write_bytes((root / "configs" / name).read_bytes())
    prepared = tmp_path / "data/processed/shiller_monthly/example"
    prepared.mkdir(parents=True)
    periods = pd.period_range("1926-01", "1989-12", freq="M").astype(str)
    table = pd.DataFrame({"asset": INSTRUMENT, "period": periods,
                          "price_monthly_mean": [100.0 + i for i in range(len(periods))],
                          "dividend_annualized": 2.4,
                          "sample_role": ["history" if p < "1927-01" else "development" for p in periods],
                          "source": "shiller"})
    table.to_parquet(prepared / "monthly.parquet", index=False)
    interval = {"history_start": "1926-01", "development_start": "1927-01", "development_end": "1989-12"}
    report = {"status": "passed", "error_counts": {}, "rows": len(table), "interval": interval}
    (prepared / "quality_report.json").write_text(json.dumps(report))
    (prepared / "validation_policy.toml").write_bytes((configs / "historical_policy.toml").read_bytes())
    (prepared / "source_manifest.json").write_text(json.dumps({"provider": "shiller", "instrument": INSTRUMENT}))
    manifest = {"schema_version": 1, "normalization_version": 1, "kind": "shiller_monthly_observations",
                "status": "passed", "instrument": INSTRUMENT, "frequency": "monthly",
                "data_file": "monthly.parquet", "quality_report": "quality_report.json", "interval": interval,
                "sha256": sha256((prepared / "monthly.parquet").read_bytes()).hexdigest(),
                "artifacts_sha256": {name: sha256((prepared / name).read_bytes()).hexdigest() for name in
                                     ("quality_report.json", "validation_policy.toml", "source_manifest.json")}}
    (prepared / "manifest.json").write_text(json.dumps(manifest))
    return configs / "shiller_signals.toml", prepared


def test_offline_cli_and_explicit_warmup(prepared_project, monkeypatch, capsys):
    config, prepared = prepared_project
    root = config.parent.parent
    before = {p.name: p.read_bytes() for p in prepared.iterdir()}
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("No debe acceder a la red"))
    assert cli.main(["build-shiller-signals", "--config", str(config), "--prepared", str(prepared)]) == 0
    run = next((root / "outputs/runs").iterdir())
    summary = json.loads((run / "summary.json").read_bytes())
    signals = pd.read_parquet(run / "signals.parquet")
    assert summary["kind"] == "shiller_mean_price_signal_diagnostics"
    assert summary["rows"] == 756 and summary["both_rules_available"] == 755
    assert summary["first_common_target"] == "1927-02"
    assert summary["missing_momentum_targets"] == ["1927-01"]
    assert summary["missing_reversal_targets"] == []
    assert signals.target_period.iloc[-1] == "1989-12"
    assert signals.decision_period.iloc[0] == "1926-12"
    assert signals.decision_period.iloc[-1] == "1989-11"
    assert pd.isna(signals.momentum_signal.iloc[0])
    assert not (run / "equity.parquet").exists()
    record = json.loads((run / "run.json").read_bytes())
    for name, expected in record["artifacts_sha256"].items():
        assert sha256((run / name).read_bytes()).hexdigest() == expected
    assert cli.main(["build-shiller-signals", "--config", str(config), "--prepared", str(prepared)]) == 0
    runs = list((root / "outputs/runs").iterdir())
    assert len(runs) == 2
    for repeated in runs:
        pd.testing.assert_frame_equal(pd.read_parquet(repeated / "signals.parquet"), signals)
        assert (repeated / "signals.csv").read_bytes() == (run / "signals.csv").read_bytes()
    assert before == {p.name: p.read_bytes() for p in prepared.iterdir()}
    output = capsys.readouterr().out
    assert "755 meses" in output and "1927-01" in output and "sin simulación" in output


@pytest.mark.parametrize("problem", ["policy", "integrity"])
def test_invalid_policy_or_changed_preparation_is_blocked(prepared_project, problem):
    config, prepared = prepared_project
    if problem == "policy":
        path = config.parent / "historical_policy.toml"
        path.write_text(path.read_text().replace("1989-12-31", "1990-12-31"))
    else:
        with (prepared / "monthly.parquet").open("ab") as handle:
            handle.write(b"changed")
    with pytest.raises(PipelineError) as error:
        run_shiller_signals(config, prepared)
    record = json.loads((error.value.run_dir / "run.json").read_bytes())
    assert record["status"] == "failed"
    assert not (error.value.run_dir / "signals.parquet").exists()
    assert not (error.value.run_dir / "summary.json").exists()


def test_publication_failure_removes_partial_outputs(prepared_project, monkeypatch):
    config, prepared = prepared_project
    def fail_csv(*args, **kwargs):
        raise OSError("CSV write failure")
    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_csv)
    with pytest.raises(PipelineError) as error:
        run_shiller_signals(config, prepared)
    run = error.value.run_dir
    record = json.loads((run / "run.json").read_bytes())
    assert record["status"] == "failed" and record["stage"] == "publication"
    assert all(not (run / name).exists() for name in ("signals.parquet", "signals.csv", "summary.json"))
    assert (run / "config.toml").exists() and (prepared / "monthly.parquet").exists()
