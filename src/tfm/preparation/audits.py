"""Verificación de una auditoría seleccionada explícitamente para una simulación."""

import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import pandas as pd

from tfm.preparation.calendar import CALENDAR_NAME, METHOD_VERSION


def load_calendar_audit(audit_dir: str | Path, manifest_bytes: bytes, policy_bytes: bytes,
                       start: str, end: str) -> tuple[dict, bytes]:
    directory = Path(audit_dir).resolve()
    record = json.loads((directory / "run.json").read_bytes())
    if record["command"] != "audit-prices" or record["status"] != "completed":
        raise ValueError("La auditoría seleccionada no es una ejecución completada de audit-prices")
    content = (directory / "audit_report.json").read_bytes()
    for name, data in (("audit_report.json", content), ("calendar_sessions.parquet", (directory / "calendar_sessions.parquet").read_bytes())):
        if hashlib.sha256(data).hexdigest() != record["artifacts_sha256"][name]:
            raise ValueError("SHA-256 incorrecto: la auditoría seleccionada ha cambiado")
    report = json.loads(content)
    manifest = json.loads(manifest_bytes)
    parameters = manifest["source_manifest"]["parameters"]
    if report["schema_version"] != 1 or report["method_version"] != METHOD_VERSION or report["scope"] != "calendar_only":
        raise ValueError("Versión o alcance de auditoría incompatible")
    binding = report["binding"]
    if (binding["prices_sha256"] != manifest["sha256"]
            or binding["prepared_manifest_sha256"] != hashlib.sha256(manifest_bytes).hexdigest()):
        raise ValueError("La auditoría no corresponde a estos precios y su manifiesto")
    if binding["policy_sha256"] != hashlib.sha256(policy_bytes).hexdigest():
        raise ValueError("La auditoría utiliza una política temporal distinta; repite la auditoría")
    if binding["config_sha256"] != record["config_sha256"]:
        raise ValueError("La configuración de la auditoría no coincide con su registro")
    if hashlib.sha256((directory / "config.toml").read_bytes()).hexdigest() != binding["config_sha256"]:
        raise ValueError("La configuración guardada de la auditoría ha cambiado")
    if (hashlib.sha256((directory / "validation_policy.toml").read_bytes()).hexdigest() != binding["policy_sha256"]
            or hashlib.sha256((directory / "prepared_manifest.json").read_bytes()).hexdigest() != binding["prepared_manifest_sha256"]):
        raise ValueError("La política o procedencia guardadas de la auditoría han cambiado")
    interval = report["interval"]
    if (interval != {"start": parameters["start"], "end_exclusive": parameters["end"]}
            or pd.Timestamp(start) < pd.Timestamp(interval["start"])
            or pd.Timestamp(end) >= pd.Timestamp(interval["end_exclusive"])):
        raise ValueError("La auditoría no cubre el intervalo completo de los datos y la simulación")
    check = report["checks"]["calendar"]
    if (check["calendar_name"] != CALENDAR_NAME or check["library_version"] != version("exchange-calendars")
            or check["tzdata_version"] != version("tzdata")):
        raise ValueError("Calendario o versión distintos; repite la auditoría con el entorno actual")
    if (check["status"] != "passed" or check["missing_sessions"] or check["unexpected_sessions"]
            or check["expected_sessions"] != check["observed_sessions"]
            or record["audit_result"] != "passed"):
        raise ValueError("La auditoría de calendario contiene discrepancias sin resolver")
    # Este incremento no puede acreditar otros campos, aunque un JSON los declare.
    if any(report["checks"][name]["status"] != "not_evaluated" for name in ("prices", "dividends", "adjustments")):
        raise ValueError("Una auditoría de calendario no acredita precios, dividendos ni ajustes")
    return report, content
