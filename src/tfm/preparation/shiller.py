"""Tabla de observaciones mensuales de Shiller; no precios de ejecución ni retornos."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
from uuid import uuid4

import pandas as pd
import xlrd

from tfm.sources.shiller import INSTRUMENT, load_shiller_snapshot
from tfm.validation.policy import parse_historical_policy


COLUMNS = ["asset", "period", "price_monthly_mean", "dividend_annualized", "sample_role", "source"]
LIMITATIONS = [
    "P es un promedio mensual nominal; no un cierre, precio de orden o cierre ajustado de SPY.",
    "D es anualizado e interpolado; no es un pago mensual ni un predictor conocido en tiempo real.",
    "Los controles son de estructura y cobertura; no certifican exactitud, disponibilidad histórica o ejecución.",
    "Rentabilidades, señales, etiquetas y metodología de ejecución quedan pendientes.",
]


class ShillerQualityError(ValueError):
    def __init__(self, message: str, report_path: Path):
        super().__init__(message)
        self.report_path = report_path


def _month(value) -> str:
    """YYYY.MM numérico: 1926.1 es octubre, no enero."""
    if isinstance(value, bool):
        raise ValueError("Mes Shiller inválido")
    try:
        number = Decimal(str(value).strip())
        scaled = number * 100
        integer = scaled.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if not number.is_finite() or abs(scaled - integer) > Decimal("0.000001"):
            raise ValueError("Fecha Shiller inválida; se esperaba YYYY.MM")
        year, month = divmod(int(integer), 100)
        if not 1800 <= year <= 2099 or not 1 <= month <= 12:
            raise ValueError("Mes Shiller fuera de rango")
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("Fecha Shiller inválida; se esperaba YYYY.MM") from exc
    return f"{year:04d}-{month:02d}"


def preparation_window(history_start: str, policy_bytes: bytes) -> tuple[str, str, str]:
    policy = parse_historical_policy(policy_bytes)
    try:
        start = pd.Period(history_start, freq="M")
    except (ValueError, TypeError) as exc:
        raise ValueError("history_start debe tener formato YYYY-MM") from exc
    if str(start) != history_start or not pd.Period("1871-01", freq="M") <= start <= pd.Period("1926-01", freq="M"):
        raise ValueError("La historia previa debe comenzar entre 1871-01 y 1926-01")
    return history_start, policy["development_start"][:7], policy["development_end"][:7]


def normalize_shiller(content: bytes, *, history_start: str, policy_bytes: bytes) -> tuple[pd.DataFrame, dict]:
    start, development_start, end = preparation_window(history_start, policy_bytes)
    try:
        book = xlrd.open_workbook(file_contents=content, on_demand=True)
    except xlrd.XLRDError as exc:
        raise ValueError("No se pudo leer el Excel XLS original de Shiller") from exc
    try:
        try:
            sheet = book.sheet_by_name("Data")
        except xlrd.XLRDError as exc:
            raise ValueError("Falta la hoja Data del Excel de Shiller") from exc
        if sheet.nrows < 9 or sheet.ncols < 3 or sheet.row_values(7, 0, 3) != ["Date", "P", "D"]:
            raise ValueError("Cabecera Shiller incompatible; revisar el adaptador antes de continuar")
        selected, original_periods = [], []
        for i in range(8, sheet.nrows):
            value = sheet.cell_value(i, 0)
            if value == "":
                continue
            period = _month(value)
            original_periods.append(period)
            if not start <= period <= end:
                continue  # No leer importes del bloque de evaluación ni otros campos.
            amounts = []
            for column in (1, 2):
                cell = sheet.cell(i, column)
                amounts.append(float(cell.value) if cell.ctype == xlrd.XL_CELL_NUMBER else float("nan"))
            selected.append({"asset": INSTRUMENT, "period": period,
                             "price_monthly_mean": amounts[0], "dividend_annualized": amounts[1],
                             "sample_role": "history" if period < development_start else "development",
                             "source": "shiller"})
    finally:
        book.release_resources()
    table = pd.DataFrame(selected, columns=COLUMNS).sort_values("period", kind="stable").reset_index(drop=True)
    expected = pd.period_range(start, end, freq="M").astype(str).tolist()
    counts = {
        "empty": int(table.empty), "duplicate_months": int(table.period.duplicated().sum()),
        "missing_months": len(set(expected) - set(table.period)),
        "non_finite_values": int(sum(not math.isfinite(value) for name in ("price_monthly_mean", "dividend_annualized") for value in table[name])),
        "non_positive_prices": int(table.price_monthly_mean.le(0).sum()),
        "negative_dividends": int(table.dividend_annualized.lt(0).sum()),
    }
    report = {
        "status": "failed" if any(counts.values()) else "passed", "scope": "structure_and_monthly_coverage_only",
        "rows": len(table), "history_rows": int(table.sample_role.eq("history").sum()),
        "development_rows": int(table.sample_role.eq("development").sum()),
        "first_period": None if table.empty else table.period.iloc[0],
        "last_period": None if table.empty else table.period.iloc[-1], "error_counts": counts,
        "missing_months": sorted(set(expected) - set(table.period)),
        "interval": {"history_start": start, "development_start": development_start, "development_end": end},
        "original_date_coverage": {"first_period": min(original_periods) if original_periods else None,
                                   "last_period": max(original_periods) if original_periods else None},
        "excluded_original_rows": len(original_periods) - len(table),
        "selected_source_columns": ["Date", "P", "D"], "warnings": LIMITATIONS,
    }
    return table, report


def prepare_shiller(snapshot_dir: str | Path, processed_root: Path, *, history_start: str, policy_bytes: bytes) -> Path:
    preparation_window(history_start, policy_bytes)  # Rechazar política/ventana antes de abrir el original.
    content, source_manifest_bytes = load_shiller_snapshot(snapshot_dir)
    source_manifest = json.loads(source_manifest_bytes)
    table, report = normalize_shiller(content, history_start=history_start, policy_bytes=policy_bytes)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    directory = processed_root / "shiller_monthly" / identifier
    directory.mkdir(parents=True, exist_ok=False)
    try:
        (directory / "source_manifest.json").write_bytes(source_manifest_bytes)
        (directory / "validation_policy.toml").write_bytes(policy_bytes)
        report["preparation_id"] = identifier
        report_path = directory / "quality_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if report["status"] == "passed":
            table.to_parquet(directory / "monthly.parquet", index=False)
        manifest = {
            "schema_version": 1, "normalization_version": 1, "kind": "shiller_monthly_observations",
            "preparation_id": identifier, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": report["status"], "instrument": INSTRUMENT, "frequency": "monthly",
            "source_snapshot_dir": str(Path(snapshot_dir).resolve()), "source_snapshot_id": source_manifest["snapshot_id"],
            "source_sha256": source_manifest["sha256"],
            "data_file": "monthly.parquet" if report["status"] == "passed" else None,
            "sha256": sha256((directory / "monthly.parquet").read_bytes()).hexdigest() if report["status"] == "passed" else None,
            "quality_report": "quality_report.json", "interval": report["interval"],
            "artifacts_sha256": {name: sha256((directory / name).read_bytes()).hexdigest()
                                 for name in ("source_manifest.json", "validation_policy.toml", "quality_report.json")},
            "versions": {name: version(name) for name in ("uoc-data-science-tfm", "pandas", "pyarrow", "xlrd")},
            "semantics": {"price_monthly_mean": "nominal monthly average index points",
                          "dividend_annualized": "annualized interpolated dividend index points; not monthly cash payment",
                          "available_at": None, "point_in_time": False, "execution_price": False},
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (Exception, KeyboardInterrupt):
        shutil.rmtree(directory)
        raise
    if report["status"] != "passed":
        raise ShillerQualityError(f"Calidad estructural insuficiente; consulte {report_path}", report_path)
    return directory


def load_shiller_monthly(directory: str | Path, policy_bytes: bytes) -> tuple[pd.DataFrame, bytes, bytes]:
    """Lectura verificada del contrato mensual; no admite las tablas diarias de SPY."""
    directory = Path(directory)
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest["schema_version"] != 1 or manifest["normalization_version"] != 1
            or manifest["kind"] != "shiller_monthly_observations" or manifest["status"] != "passed"
            or manifest["instrument"] != INSTRUMENT or manifest["frequency"] != "monthly"
            or manifest["data_file"] != "monthly.parquet" or manifest["quality_report"] != "quality_report.json"):
        raise ValueError("La preparación no es una tabla mensual Shiller compatible y aprobada")
    files = {name: (directory / name).read_bytes() for name in
             ("source_manifest.json", "validation_policy.toml", "quality_report.json")}
    if any(sha256(data).hexdigest() != manifest["artifacts_sha256"][name] for name, data in files.items()):
        raise ValueError("SHA-256 incorrecto en la procedencia o calidad de la tabla mensual")
    if files["validation_policy.toml"] != policy_bytes:
        raise ValueError("La tabla mensual utiliza otra política temporal")
    interval = manifest["interval"]
    start, development_start, end = preparation_window(interval["history_start"], policy_bytes)
    if interval != {"history_start": start, "development_start": development_start, "development_end": end}:
        raise ValueError("El intervalo mensual no coincide con la política")
    content = (directory / "monthly.parquet").read_bytes()
    if sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("SHA-256 incorrecto: la tabla mensual ha cambiado")
    table = pd.read_parquet(BytesIO(content))
    report = json.loads(files["quality_report.json"])
    if (report["status"] != "passed" or any(report["error_counts"].values())
            or report["interval"] != interval or report["rows"] != len(table)
            or table.columns.tolist() != COLUMNS
            or table.period.tolist() != pd.period_range(start, end, freq="M").astype(str).tolist()
            or not table.asset.eq(INSTRUMENT).all() or not table.source.eq("shiller").all()
            or table.sample_role.tolist() != ["history" if p < development_start else "development" for p in table.period]):
        raise ValueError("La tabla mensual o su cobertura no cumplen el contrato de desarrollo")
    for name in ("price_monthly_mean", "dividend_annualized"):
        values = table[name]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or not values.map(math.isfinite).all()
                or (values.le(0).any() if name == "price_monthly_mean" else values.lt(0).any())):
            raise ValueError("Valores mensuales no válidos")
    return table, manifest_bytes, files["quality_report.json"]
