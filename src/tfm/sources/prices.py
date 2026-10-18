"""Descarga de precios diarios y snapshots trazables, sin normalización."""

from datetime import date, datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import tomllib
from uuid import uuid4

import pandas as pd
import yfinance as yf


class DownloadError(RuntimeError):
    """El proveedor no devolvió una respuesta utilizable."""


REQUIRED_COLUMNS = {
    "Open", "High", "Low", "Close", "Adj Close", "Volume",
    "Dividends", "Stock Splits",
}


def fetch_prices(parameters: dict) -> pd.DataFrame:
    """Obtener precios de Yahoo sin persistir snapshots ni registros."""
    start, end = parameters["start"], parameters["end"]
    try:
        frame = yf.download(**parameters)
    except Exception as exc:
        raise DownloadError("La descarga de Yahoo ha fallado") from exc
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise DownloadError("Yahoo no devolvió precios; no se ha creado un snapshot")
    if isinstance(frame.columns, pd.MultiIndex) or not REQUIRED_COLUMNS.issubset(frame.columns):
        raise DownloadError("La respuesta no contiene las columnas de precios y eventos esperadas")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans or frame.index.tz is not None:
        raise DownloadError("Se esperaba un índice de fechas de sesión sin zona horaria")
    if (frame.index < pd.Timestamp(start)).any() or (frame.index >= pd.Timestamp(end)).any():
        raise DownloadError("La respuesta contiene fechas fuera del periodo solicitado")
    if any(not pd.api.types.is_numeric_dtype(frame[column]) for column in REQUIRED_COLUMNS):
        raise DownloadError("La respuesta contiene campos financieros no numéricos")
    return frame


def download_prices(config_path: str | Path) -> Path:
    """Guardar una descarga y su manifiesto; devolver su directorio.

    Las rutas relativas de almacenamiento parten de la raíz del proyecto
    (el padre de configs). No se corrigen ni imputan datos aquí.
    """
    config_path = Path(config_path).resolve()
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    market = config["market"]
    options = config["download"]
    if market["provider"] != "yahoo" or market["frequency"] != "daily":
        raise ValueError("Solo se admite Yahoo con precios diarios")
    if market["instrument"] != "SPY":
        raise ValueError("Este primer adaptador solo admite SPY")
    start, end = market["start"], market["end"]
    if date.fromisoformat(start) >= date.fromisoformat(end):
        raise ValueError("El inicio debe preceder al fin exclusivo")
    expected = {
        "interval": "1d", "auto_adjust": False, "back_adjust": False,
        "actions": True, "repair": False, "keepna": True,
        "rounding": False, "prepost": False, "threads": False,
        "multi_level_index": False, "ignore_tz": True,
    }
    if set(options) != set(expected) | {"timeout"} or any(
        type(options[key]) is not type(value) or options[key] != value
        for key, value in expected.items()
    ):
        raise ValueError("Los parámetros deben conservar precios y eventos diarios sin ajustes propios")
    if isinstance(options["timeout"], bool) or not isinstance(options["timeout"], (int, float)) or not 0 < options["timeout"] <= 120:
        raise ValueError("timeout debe estar entre 0 y 120 segundos")
    parameters = {"tickers": market["instrument"], "start": start, "end": end,
                  **options, "progress": False, "group_by": "column"}
    requested_at = datetime.now(timezone.utc).isoformat()
    frame = fetch_prices(parameters)
    # Ausentes, duplicados y coherencia económica se informarán en preparation.
    raw_root = Path(config["storage"]["raw"])
    if not raw_root.is_absolute():
        raw_root = config_path.parent.parent / raw_root
    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    directory = raw_root / "yahoo" / "SPY" / snapshot_id
    directory.mkdir(parents=True, exist_ok=False)
    try:
        data_path = directory / "prices.parquet"
        frame.to_parquet(data_path, engine="pyarrow", index=True)
        manifest = {
            "schema_version": 1, "snapshot_id": snapshot_id,
            "provider": "yahoo", "instrument": "SPY",
            "requested_at_utc": requested_at,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters, "config": config,
            "versions": {name: version(name) for name in ("yfinance", "pandas", "pyarrow")},
            "data_file": "prices.parquet",
            "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
            "rows": len(frame), "columns": list(frame.columns),
            "first_session": frame.index.min().isoformat(),
            "last_session": frame.index.max().isoformat(),
            "meaning": "Respuesta de yfinance serializada; no es el payload HTTP ni historia point-in-time",
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(directory)
        raise
    return directory
