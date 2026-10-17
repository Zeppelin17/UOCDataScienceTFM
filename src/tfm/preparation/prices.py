"""Normalización de un snapshot SPY con controles explícitos de calidad."""

from datetime import datetime, timezone
import hashlib
from io import BytesIO
from importlib.metadata import version
import json
from pathlib import Path
import shutil
from uuid import uuid4

import pandas as pd

from tfm.backtesting.engine import validate_prices
from tfm.preparation.quality import pending_checks


COLUMN_NAMES = {
    "Open": "open", "High": "high", "Low": "low", "Close": "close",
    "Adj Close": "adjusted_close", "Volume": "volume",
    "Dividends": "dividends", "Stock Splits": "stock_splits",
}
SCHEMA_VERSION = 1


class PriceQualityError(ValueError):
    """Datos rechazados; report_path indica el informe si pudo generarse."""

    def __init__(self, message: str, report_path: Path | None = None):
        super().__init__(message)
        self.report_path = report_path


def normalize_prices(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cambiar nombres y ordenar sesiones sin imputar ni eliminar filas.

    Devuelve la tabla y un informe. Los errores del informe bloquean su
    publicación; los errores de estructura impiden incluso normalizarla.
    """
    if isinstance(frame.columns, pd.MultiIndex) or not frame.columns.is_unique:
        raise PriceQualityError("Se esperaban columnas simples y únicas")
    if not set(COLUMN_NAMES).issubset(frame.columns):
        raise PriceQualityError("Faltan campos de precios o eventos")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is not None:
        raise PriceQualityError("Se esperaban fechas de sesión sin zona horaria")
    for column in COLUMN_NAMES:
        dtype = frame[column].dtype
        if not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
            raise PriceQualityError(f"Campo no numérico: {column}")
    table = frame[list(COLUMN_NAMES)].rename(columns=COLUMN_NAMES).copy()
    table.insert(0, "observed_at", frame.index)
    table.insert(0, "asset", "SPY")
    table["source"] = "yahoo"
    table = table.sort_values("observed_at", kind="stable").reset_index(drop=True)
    numeric = table[list(COLUMN_NAMES.values())]
    prices = table[["open", "high", "low", "close", "adjusted_close"]]
    bad_ohlc = (
        (table["low"] > table["high"])
        | (table["open"] < table["low"]) | (table["open"] > table["high"])
        | (table["close"] < table["low"]) | (table["close"] > table["high"])
    )
    counts = {
        "empty": int(table.empty),
        "missing_dates": int(table["observed_at"].isna().sum()),
        "duplicate_sessions": int(table.duplicated(["asset", "observed_at"]).sum()),
        "non_daily_dates": int((table["observed_at"] != table["observed_at"].dt.normalize()).sum()),
        "non_finite_values": int((numeric.isna() | numeric.isin([float("inf"), float("-inf")])).sum().sum()),
        "non_positive_prices": int((prices <= 0).sum().sum()),
        "negative_volume": int((table["volume"] < 0).sum()),
        "negative_dividends": int((table["dividends"] < 0).sum()),
        "negative_stock_splits": int((table["stock_splits"] < 0).sum()),
        "inconsistent_ohlc": int(bad_ohlc.sum()),
    }
    report = {
        "status": "failed" if any(counts.values()) else "passed",
        "rows": len(table), "error_counts": counts,
        "missing_by_column": {key: int(value) for key, value in numeric.isna().sum().items()},
        "first_session": table["observed_at"].min().isoformat() if table["observed_at"].notna().any() else None,
        "last_session": table["observed_at"].max().isoformat() if table["observed_at"].notna().any() else None,
        "input_was_sorted": frame.index.is_monotonic_increasing,
        "checks": pending_checks(),
        "warnings": [],
    }
    return table, report


def prepare_prices(snapshot_dir: str | Path, processed_root: str | Path) -> Path:
    """Verificar SHA-256 y publicar una tabla preparada o un informe fallido.

    processed_root es explícito; las rutas relativas parten del directorio
    de ejecución. Cada intento con estructura válida crea un directorio nuevo.
    """
    snapshot_dir = Path(snapshot_dir).resolve()
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["schema_version"] != 1 or manifest["provider"] != "yahoo"
            or manifest["instrument"] != "SPY" or manifest["data_file"] != "prices.parquet"):
        raise PriceQualityError("El manifiesto no corresponde a un snapshot SPY compatible")
    data_path = snapshot_dir / "prices.parquet"
    checksum = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if checksum != manifest["sha256"]:
        raise PriceQualityError("SHA-256 incorrecto: el snapshot ha cambiado")
    frame = pd.read_parquet(data_path)
    if len(frame) != manifest["rows"]:
        raise PriceQualityError("El número de filas no coincide con el manifiesto")
    table, report = normalize_prices(frame)
    start = pd.Timestamp(manifest["parameters"]["start"])
    end = pd.Timestamp(manifest["parameters"]["end"])
    if pd.isna(start) or pd.isna(end) or start >= end:
        raise PriceQualityError("Intervalo inválido en el manifiesto")
    outside = int(((table["observed_at"] < start) | (table["observed_at"] >= end)).sum())
    report["error_counts"]["outside_requested_period"] = outside
    report["status"] = "failed" if any(report["error_counts"].values()) else "passed"
    preparation_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    directory = Path(processed_root).resolve() / "prices" / preparation_id
    directory.mkdir(parents=True, exist_ok=False)
    try:
        report["preparation_id"] = preparation_id
        report_path = directory / "quality_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        prepared_checksum = None
        if report["status"] == "passed":
            output_path = directory / "prices.parquet"
            table.to_parquet(output_path, engine="pyarrow", index=False)
            prepared_checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()
        provenance = {
            "schema_version": SCHEMA_VERSION, "preparation_id": preparation_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": report["status"], "source_snapshot_dir": str(snapshot_dir),
            "source_snapshot_id": manifest["snapshot_id"], "source_sha256": checksum,
            "source_manifest": manifest,
            "data_file": "prices.parquet" if prepared_checksum else None,
            "sha256": prepared_checksum, "quality_report": "quality_report.json",
            "versions": {name: version(name) for name in ("pandas", "pyarrow", "uoc-data-science-tfm")},
            "normalization_version": 1,
        }
        (directory / "manifest.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(directory)
        raise
    if report["status"] == "failed":
        raise PriceQualityError(f"Calidad insuficiente; consulte {report_path}", report_path)
    return directory


def load_prepared_prices(directory: str | Path) -> tuple[pd.DataFrame, bytes, bytes]:
    """Verificar una preparación sin modificarla; leer los mismos bytes cuya huella se comprueba."""
    directory = Path(directory)
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest["schema_version"] != 1 or manifest["status"] != "passed"
            or manifest["normalization_version"] != 1 or manifest["data_file"] != "prices.parquet"
            or manifest["quality_report"] != "quality_report.json"
            or manifest["source_manifest"]["instrument"] != "SPY"
            or manifest["source_manifest"]["provider"] != "yahoo"):
        raise ValueError("La preparación no corresponde a precios SPY compatibles y aprobados")
    report_bytes = (directory / "quality_report.json").read_bytes()
    report = json.loads(report_bytes)
    if report["status"] != "passed" or any(report["error_counts"].values()):
        raise ValueError("La preparación no ha superado los controles de calidad")
    content = (directory / "prices.parquet").read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("SHA-256 incorrecto: los precios preparados han cambiado")
    prices = pd.read_parquet(BytesIO(content))
    validate_prices(prices)
    if len(prices) != report["rows"]:
        raise ValueError("El número de filas no coincide con el informe de calidad")
    parameters = manifest["source_manifest"]["parameters"]
    start, end = pd.Timestamp(parameters["start"]), pd.Timestamp(parameters["end"])
    if (pd.isna(start) or pd.isna(end) or start.tz is not None or end.tz is not None
            or start != start.normalize() or end != end.normalize() or start >= end):
        raise ValueError("Intervalo solicitado inválido en el manifiesto")
    if not ((prices["observed_at"] >= start) & (prices["observed_at"] < end)).all():
        raise ValueError("La preparación contiene fechas fuera del intervalo solicitado")
    return prices, manifest_bytes, report_bytes
