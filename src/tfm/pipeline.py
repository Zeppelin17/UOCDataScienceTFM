"""Primer flujo reproducible: descarga, preparación y registro de ejecución."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import tomllib
from uuid import uuid4

from tfm.preparation.prices import prepare_prices
from tfm.sources.prices import download_prices


class PipelineError(RuntimeError):
    """Fallo de ejecución con un registro consultable."""

    def __init__(self, message: str, run_dir: Path):
        super().__init__(message)
        self.run_dir = run_dir


def _git_state(project_root: Path) -> dict:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=project_root,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout
        return {"commit": revision, "dirty": bool(status)}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def _write_record(path: Path, record: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_prepare_prices(config_path: str | Path, snapshot_dir: str | Path | None = None) -> Path:
    """Ejecutar el flujo y devolver outputs/runs/<run_id>.

    Un snapshot explícito permite repetir la preparación sin acceder a Yahoo.
    Sus parámetros deben coincidir con los solicitados en la configuración.
    """
    config_path = Path(config_path).resolve()
    project_root = config_path.parent.parent
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    run_dir = project_root / "outputs" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    record_path = run_dir / "run.json"
    record = {
        "schema_version": 1, "run_id": run_id, "command": "prepare-prices",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running", "stage": "configuration",
        "config_path": str(config_path), "snapshot_dir": None,
        "prepared_dir": None, "git": _git_state(project_root),
        "versions": {name: version(name) for name in ("uoc-data-science-tfm", "yfinance", "pandas", "pyarrow")},
    }
    _write_record(record_path, record)
    try:
        config_bytes = config_path.read_bytes()
        (run_dir / "config.toml").write_bytes(config_bytes)
        config = tomllib.loads(config_bytes.decode("utf-8"))
        record["config_sha256"] = hashlib.sha256(config_bytes).hexdigest()
        storage = {}
        for key in ("raw", "processed"):
            path = Path(config["storage"][key])
            storage[key] = str((project_root / path).resolve())
        record["resolved_storage"] = storage
        record["stage"] = "download" if snapshot_dir is None else "snapshot_validation"
        _write_record(record_path, record)
        if snapshot_dir is None:
            snapshot = download_prices(config_path)
        else:
            snapshot = Path(snapshot_dir).resolve()
            record["snapshot_dir"] = str(snapshot)
            manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
            market = config["market"]
            expected_parameters = {
                "tickers": market["instrument"], "start": market["start"],
                "end": market["end"], **config["download"],
                "progress": False, "group_by": "column",
            }
            if (market["provider"] != manifest["provider"]
                    or market["frequency"] != "daily"
                    or expected_parameters != manifest["parameters"]):
                raise ValueError("El snapshot no coincide con los parámetros de la configuración")
        record["snapshot_dir"] = str(snapshot)
        record["stage"] = "preparation"
        _write_record(record_path, record)
        prepared = prepare_prices(snapshot, storage["processed"])
        record["prepared_dir"] = str(prepared)
        # Copias de los manifiestos facilitan consultar la procedencia del run.
        for name, directory in (("source_manifest.json", snapshot), ("prepared_manifest.json", prepared)):
            (run_dir / name).write_bytes((directory / "manifest.json").read_bytes())
        (run_dir / "quality_report.json").write_bytes((prepared / "quality_report.json").read_bytes())
        record["status"] = "completed"
        record["stage"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if getattr(exc, "report_path", None) is not None:
            record["quality_report_path"] = str(exc.report_path)
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write_record(record_path, record)
        raise PipelineError(f"{exc}\nRegistro: {record_path}", run_dir) from exc
    record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_record(record_path, record)
    return run_dir
