"""Primer flujo reproducible: descarga, preparación y registro de ejecución."""

from datetime import datetime, timezone
from datetime import date, timedelta
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import subprocess
import tomllib
from uuid import uuid4

import pandas as pd

from tfm.backtesting.buy_and_hold import simulate_buy_and_hold
from tfm.backtesting.engine import validate_prices
from tfm.evaluation.simulation import summarize_simulation
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


def load_buy_and_hold_config(config_path: str | Path) -> dict:
    """Validar convenciones e intervalo; compartir la política temporal existente.

    Las rutas declaradas en TOML parten de la raíz deducida de configs/.
    El contenido exacto de ambos TOML se devuelve para registrar su procedencia.
    """
    path = Path(config_path).resolve()
    config_bytes = path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    simulation = config["simulation"]
    conventions = {
        "instrument": "SPY", "execution": "next_session_close",
        "return_basis": "adjusted_close", "cash_rate": 0.0,
        "liquidate_at_end": False,
    }
    if set(simulation) != set(conventions) | {"start", "end", "cost_bps"}:
        raise ValueError("La configuración de simulación contiene campos ausentes o desconocidos")
    for key, expected in conventions.items():
        if simulation[key] != expected:
            raise ValueError(f"Convención no implementada: {key}={simulation[key]}")
    if type(simulation["liquidate_at_end"]) is not bool or isinstance(simulation["cash_rate"], bool):
        raise ValueError("Tipos incorrectos para liquidación o remuneración del efectivo")
    start = date.fromisoformat(simulation["start"])
    end = date.fromisoformat(simulation["end"])
    if start >= end:
        raise ValueError("El inicio debe ser anterior al final inclusivo")
    cost = simulation["cost_bps"]
    if (isinstance(cost, bool) or not isinstance(cost, (int, float))
            or not math.isfinite(cost) or not 0 <= cost < 10000):
        raise ValueError("El coste debe ser finito, no negativo y menor que 10.000 puntos básicos")
    root = path.parent.parent
    policy_path = (root / config["validation"]["policy_config"]).resolve()
    policy_bytes = policy_path.read_bytes()
    policy = tomllib.loads(policy_bytes.decode("utf-8"))["validation"]
    development_end = date.fromisoformat(policy["development_end"])
    final_start = date.fromisoformat(policy["final_test_start"])
    if development_end + timedelta(days=1) != final_start:
        raise ValueError("La política debe separar desarrollo y periodo final sin huecos ni solapamientos")
    if end > development_end:
        raise ValueError("El intervalo invade el periodo reservado para evaluación final")
    return {
        "root": root, "config_bytes": config_bytes, "simulation": simulation,
        "policy_path": policy_path, "policy_bytes": policy_bytes,
        "development_end": development_end.isoformat(),
        "final_test_start": final_start.isoformat(),
        "processed_root": (root / config["storage"]["processed"]).resolve(),
    }


def run_buy_and_hold(config_path: str | Path, prepared_dir: str | Path) -> Path:
    """Simular una preparación explícita sin red y registrar cada intento."""
    config_path = Path(config_path).resolve()
    prepared_dir = Path(prepared_dir).resolve()
    root = config_path.parent.parent
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    run_dir = root / "outputs" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    record_path = run_dir / "run.json"
    record = {
        "schema_version": 1, "run_id": run_id, "command": "simulate-buy-and-hold",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running", "stage": "configuration", "git": _git_state(root),
        "config_path": str(config_path), "prepared_dir": str(prepared_dir),
        "versions": {name: version(name) for name in ("uoc-data-science-tfm", "pandas", "pyarrow")},
    }
    _write_record(record_path, record)
    try:
        # Conservar también una configuración inválida si el archivo existe.
        (run_dir / "config.toml").write_bytes(config_path.read_bytes())
        settings = load_buy_and_hold_config(config_path)
        (run_dir / "config.toml").write_bytes(settings["config_bytes"])
        (run_dir / "validation_policy.toml").write_bytes(settings["policy_bytes"])
        record.update({
            "config_sha256": hashlib.sha256(settings["config_bytes"]).hexdigest(),
            "policy_sha256": hashlib.sha256(settings["policy_bytes"]).hexdigest(),
            "policy_path": str(settings["policy_path"]),
            "development_end": settings["development_end"],
            "final_test_start": settings["final_test_start"],
            "stage": "prepared_validation",
        })
        _write_record(record_path, record)
        manifest_bytes = (prepared_dir / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        if (manifest["schema_version"] != 1 or manifest["status"] != "passed"
                or manifest["normalization_version"] != 1 or manifest["data_file"] != "prices.parquet"
                or manifest["quality_report"] != "quality_report.json"
                or manifest["source_manifest"]["instrument"] != "SPY"
                or manifest["source_manifest"]["provider"] != "yahoo"):
            raise ValueError("La preparación no corresponde a precios SPY compatibles y aprobados")
        report_bytes = (prepared_dir / "quality_report.json").read_bytes()
        report = json.loads(report_bytes)
        if report["status"] != "passed" or any(report["error_counts"].values()):
            raise ValueError("La preparación no ha superado los controles de calidad")
        data_path = prepared_dir / "prices.parquet"
        data_bytes = data_path.read_bytes()
        if hashlib.sha256(data_bytes).hexdigest() != manifest["sha256"]:
            raise ValueError("SHA-256 incorrecto: los precios preparados han cambiado")
        # Leer los mismos bytes que se han verificado, evitando cambios entre lecturas.
        from io import BytesIO
        prices = pd.read_parquet(BytesIO(data_bytes))
        validate_prices(prices)
        if len(prices) != report["rows"]:
            raise ValueError("El número de filas no coincide con el informe de calidad")
        dates = prices["observed_at"]
        if dates.gt(pd.Timestamp(settings["development_end"])).any():
            raise ValueError("La preparación contiene datos del periodo reservado para evaluación final")
        simulation = settings["simulation"]
        start, end = pd.Timestamp(simulation["start"]), pd.Timestamp(simulation["end"])
        if start < dates.iloc[0] or end > dates.iloc[-1]:
            raise ValueError("El intervalo solicitado excede la cobertura de los precios preparados")
        selected = prices.loc[dates.between(start, end)].reset_index(drop=True)
        (run_dir / "prepared_manifest.json").write_bytes(manifest_bytes)
        (run_dir / "quality_report.json").write_bytes(report_bytes)
        record["stage"] = "simulation"
        _write_record(record_path, record)
        equity = simulate_buy_and_hold(selected, cost_bps=simulation["cost_bps"])
        summary = summarize_simulation(equity)
        summary["assumptions"] = simulation
        summary["warnings"] = list(report.get("warnings", [])) + [
            "Cierre ajustado como aproximación a rentabilidad total; no precio de ejecución real.",
            "Coste ilustrativo, efectivo sin remuneración y sin liquidación final.",
            "Sesiones según el archivo: calendario completo y contraste independiente pendientes.",
        ]
        record["stage"] = "publication"
        _write_record(record_path, record)
        equity_path = run_dir / "equity.parquet"
        temporary = run_dir / "equity.tmp.parquet"
        equity.to_parquet(temporary, index=False)
        temporary.replace(equity_path)
        _write_record(run_dir / "summary.json", summary)
        record.update({
            "status": "completed", "stage": "completed", "engine_version": 1,
            "equity_path": str(equity_path), "summary_path": str(run_dir / "summary.json"),
            "artifacts_sha256": {
                name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
                for name in ("equity.parquet", "summary.json")
            },
        })
    except (Exception, KeyboardInterrupt) as exc:
        for name in ("equity.tmp.parquet", "equity.parquet", "summary.json", "summary.tmp"):
            (run_dir / name).unlink(missing_ok=True)
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write_record(record_path, record)
        raise PipelineError(f"{exc}\nRegistro: {record_path}", run_dir) from exc
    record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_record(record_path, record)
    return run_dir
