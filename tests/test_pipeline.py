import json
from pathlib import Path

import pandas as pd

from tfm.cli import main
from tfm.sources import prices


def setup_project(tmp_path, monkeypatch, *, duplicate=False):
    directory = tmp_path / "configs"
    directory.mkdir()
    config = directory / "data.toml"
    config.write_text((Path(__file__).parents[1] / "configs/data.toml").read_text())
    frame = pd.DataFrame({
        "Open": [100.0, 101.0], "High": [102.0, 103.0],
        "Low": [99.0, 100.0], "Close": [101.0, 102.0],
        "Adj Close": [100.0, 101.0], "Volume": [1000, 2000],
        "Dividends": [0.0, 1.0], "Stock Splits": [0.0, 0.0],
    }, index=pd.to_datetime(["2020-12-30", "2020-12-30" if duplicate else "2020-12-31"]))
    monkeypatch.setattr(prices.yf, "download", lambda **kwargs: frame)
    return config


def test_cli_pipeline_and_offline_replay(tmp_path, monkeypatch):
    config = setup_project(tmp_path, monkeypatch)
    assert main(["prepare-prices", "--config", str(config)]) == 0
    first_run = next((tmp_path / "outputs/runs").iterdir())
    record = json.loads((first_run / "run.json").read_text())
    assert record["status"] == "completed"
    assert (first_run / "config.toml").read_bytes() == config.read_bytes()
    assert (first_run / "source_manifest.json").exists()
    assert (first_run / "quality_report.json").exists()
    def unexpected_download(**kwargs):
        raise AssertionError("La repetición no debe acceder a Yahoo")
    monkeypatch.setattr(prices.yf, "download", unexpected_download)
    assert main(["prepare-prices", "--config", str(config), "--snapshot", record["snapshot_dir"]]) == 0
    other_run = next(path for path in (tmp_path / "outputs/runs").iterdir() if path != first_run)
    replay = json.loads((other_run / "run.json").read_text())
    assert replay["prepared_dir"] != record["prepared_dir"]
    pd.testing.assert_frame_equal(
        pd.read_parquet(Path(record["prepared_dir"]) / "prices.parquet"),
        pd.read_parquet(Path(replay["prepared_dir"]) / "prices.parquet"),
    )


def test_cli_records_failed_quality_and_returns_error(tmp_path, monkeypatch, capsys):
    config = setup_project(tmp_path, monkeypatch, duplicate=True)
    assert main(["prepare-prices", "--config", str(config)]) == 1
    run = next((tmp_path / "outputs/runs").iterdir())
    record = json.loads((run / "run.json").read_text())
    assert record["status"] == "failed"
    assert record["stage"] == "preparation"
    assert record["prepared_dir"] is None
    assert Path(record["snapshot_dir"]).exists()
    report_path = Path(record["quality_report_path"])
    assert json.loads(report_path.read_text())["status"] == "failed"
    assert not (report_path.parent / "prices.parquet").exists()
    assert "Registro:" in capsys.readouterr().err
