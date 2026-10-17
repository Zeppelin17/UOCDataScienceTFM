"""Adaptador concreto del listado histórico de distribuciones de State Street.

El XLSX original se archiva entero. Solo se normalizan importes de SPY dentro
de la ventana de desarrollo explícita, nunca importes del periodo reservado.
"""

from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
import math
import shutil
from pathlib import Path
from zipfile import BadZipFile
from uuid import uuid4
import tomllib

from openpyxl import load_workbook
import pandas as pd


SOURCE_URL = "https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx"
LANDING_URL = "https://www.ssga.com/us/en/intermediary/resources/documents/etf-dividend-distributions"
HEADERS = (
    "FUND NAME", "TICKER", "CUSIP", "EX-DATE", "RECORD DATE", "PAYABLE DATE",
    "DIVIDEND ($)", "SHORT TERM CAPITAL GAIN ($)", "LONG TERM CAPITAL GAIN ($)", "FREQUENCY",
)


def parse_distributions(content: bytes, start: str, end_exclusive: str) -> tuple[pd.DataFrame, dict]:
    start, end = pd.Timestamp(start), pd.Timestamp(end_exclusive)
    if start >= end or start < pd.Timestamp("1993-01-29"):
        raise ValueError("Ventana de referencia inválida para SPY")
    try:
        book = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except BadZipFile as exc:
        raise ValueError("El fichero no es un Excel XLSX válido de State Street") from exc
    try:
        rows = iter(book["dividend"].values)
        if tuple(next(rows)) != HEADERS:
            raise ValueError("Cabecera del Excel SSGA incompatible; revisar el adaptador")
        selected, dates, excluded = [], [], 0
        for row in rows:
            if row[1] != "SPY":
                continue
            if row[2] != "78462F103":
                raise ValueError("CUSIP de SPY inesperado en la referencia")
            when = pd.Timestamp(datetime.strptime(str(row[3]).strip(), "%m/%d/%Y"))
            dates.append(when)
            if not start <= when < end:
                excluded += 1
                continue  # No interpretar importes fuerade la ventana autorizada.
            amounts = [0.0 if value is None or str(value).strip() == "" else float(value) for value in row[6:9]]
            if not all(math.isfinite(value) for value in amounts) or min(amounts) < 0 or sum(amounts) <= 0:
                raise ValueError(f"Distribución SSGA inválida en {when.date()}")
            selected.append({"observed_at": when, "income_dividend": amounts[0],
                             "short_term_gain": amounts[1], "long_term_gain": amounts[2]})
    finally:
        book.close()
    if not dates or not selected or len(set(dates)) != len(dates):
        raise ValueError("Referencia SPY vacía o con fechas exdividendo duplicadas")
    # Una descarga truncada no debe simular un listado de historia completa.
    # Las fechas de eventos NO sustituyen el intervalo explícito de cobertura.
    if min(dates) != pd.Timestamp("1993-03-19") or max(dates) < end:
        raise ValueError("El listado no acredita historia desde 1993 y vigencia posterior al intervalo solicitado")
    frame = pd.DataFrame(selected).sort_values("observed_at").reset_index(drop=True)
    frame["cash_distribution"] = frame[["income_dividend", "short_term_gain", "long_term_gain"]].sum(axis=1)
    return frame, {"start": str(start.date()), "end_exclusive": str(end.date()),
                   "basis": "explicit_window_in_issuer_historical_listing",
                   "original_first_ex_date": str(min(dates).date()),
                   "original_last_ex_date": str(max(dates).date()),
                   "excluded_spy_rows": excluded,
                   "limitation": "Cobertura del listado recibido, no certificación independiente de que el emisor publique todos los eventos."}


def import_reference(file: str | Path, raw_root: Path, start: str, end: str,
                     config_bytes: bytes, policy_bytes: bytes) -> Path:
    """Archivar una exportación elegida por el usuario, sin modificarla ni descargarla."""
    policy = tomllib.loads(policy_bytes.decode())["validation"]
    if pd.Timestamp(end) > pd.Timestamp(policy["final_test_start"]):
        raise ValueError("La ventana de referencia invade el periodo reservado")
    expected = {"provider": "ssga_dividends", "start": start, "end": end}
    if tomllib.loads(config_bytes.decode())["reference"] != expected:
        raise ValueError("La ventana no coincide con la configuración de importación")
    content = Path(file).read_bytes()
    frame, coverage = parse_distributions(content, start, end)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    directory = raw_root / "ssga" / "SPY" / identifier
    directory.mkdir(parents=True, exist_ok=False)
    try:
        (directory / "original.xlsx").write_bytes(content)
        (directory / "config.toml").write_bytes(config_bytes)
        (directory / "validation_policy.toml").write_bytes(policy_bytes)
        frame.to_parquet(directory / "dividends.parquet", index=False)
        manifest = {
            "schema_version": 1, "adapter_version": 1, "status": "completed",
            "snapshot_id": identifier, "provider": "ssga_dividends", "instrument": "SPY", "currency": "USD",
            "source_url": SOURCE_URL, "landing_url": LANDING_URL, "input_path": str(Path(file).resolve()),
            "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
            "acquisition": "local_export_import; timestamp is import time, not asserted download time",
            "coverage": coverage, "rows": len(frame), "date_basis": "ex_date",
            "transformation": "income + short_term_capital_gain + long_term_capital_gain; no rounding",
            "independence": "Issuer publication, obtained without Yahoo; Yahoo upstream lineage unknown, independence of upstream processing not proven.",
            "versions": {name: version(name) for name in ("pandas", "pyarrow", "openpyxl")},
            "artifacts_sha256": {name: sha256((directory / name).read_bytes()).hexdigest()
                                 for name in ("original.xlsx", "dividends.parquet", "config.toml", "validation_policy.toml")},
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    except (Exception, KeyboardInterrupt):
        shutil.rmtree(directory)
        raise
    return directory


def load_reference(directory: str | Path, policy_bytes: bytes) -> tuple[pd.DataFrame, bytes]:
    directory = Path(directory).resolve()
    content = (directory / "manifest.json").read_bytes()
    manifest = json.loads(content)
    if (manifest["schema_version"] != 1 or manifest["adapter_version"] != 1
            or manifest["status"] != "completed" or manifest["provider"] != "ssga_dividends"
            or manifest["instrument"] != "SPY" or manifest["currency"] != "USD"
            or manifest["date_basis"] != "ex_date"):
        raise ValueError("Referencia SSGA incompatible")
    files = {name: (directory / name).read_bytes() for name in
             ("original.xlsx", "dividends.parquet", "config.toml", "validation_policy.toml")}
    if any(sha256(data).hexdigest() != manifest["artifacts_sha256"][name] for name, data in files.items()):
        raise ValueError("SHA-256 incorrecto en la referencia SSGA")
    if files["validation_policy.toml"] != policy_bytes:
        raise ValueError("La referencia utiliza otra política temporal; impórtala de nuevo")
    coverage = manifest["coverage"]
    config = tomllib.loads(files["config.toml"].decode())
    if config["reference"] != {"provider": "ssga_dividends", "start": coverage["start"], "end": coverage["end_exclusive"]}:
        raise ValueError("La cobertura no coincide con la configuración de importación")
    policy = tomllib.loads(policy_bytes.decode())["validation"]
    if pd.Timestamp(coverage["end_exclusive"]) > pd.Timestamp(policy["final_test_start"]):
        raise ValueError("La referencia normalizada invade el periodo reservado")
    expected, actual_coverage = parse_distributions(files["original.xlsx"], coverage["start"], coverage["end_exclusive"])
    frame = pd.read_parquet(BytesIO(files["dividends.parquet"]))
    if actual_coverage != coverage or len(frame) != manifest["rows"]:
        raise ValueError("La cobertura de referencia no coincide con su original")
    try:
        pd.testing.assert_frame_equal(frame, expected, check_exact=True)
    except AssertionError as exc:
        raise ValueError("La referencia normalizada no reproduce el Excel original") from exc
    return frame, content
