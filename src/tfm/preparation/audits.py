"""Verificación de una auditoría seleccionada explícitamente para una simulación."""

import hashlib
from importlib.metadata import version
import json
from io import BytesIO
import tomllib
from pathlib import Path

import pandas as pd

from tfm.preparation.calendar import CALENDAR_NAME, METHOD_VERSION
from tfm.sources.ssga import load_reference
from tfm.preparation.reconciliation import ABSOLUTE_TOLERANCE_USD, RECONCILIATION_VERSION, reconcile_dividends


def load_calendar_audit(audit_dir: str | Path, manifest_bytes: bytes, policy_bytes: bytes,
                       start: str, end: str, *, prices: pd.DataFrame | None = None) -> tuple[dict, bytes]:
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
    schema = report["schema_version"]
    scopes = {1: "calendar_only", 2: "calendar_and_distributions"}
    if schema not in scopes or report["method_version"] != METHOD_VERSION or report["scope"] != scopes[schema]:
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
            or (schema == 1 and record["audit_result"] != "passed")):
        raise ValueError("La auditoría de calendario contiene discrepancias sin resolver")
    if schema == 1:
        if any(report["checks"][name]["status"] != "not_evaluated" for name in ("prices", "dividends", "adjustments")):
            raise ValueError("Una auditoría de calendario no acredita precios, dividendos ni ajustes")
    else:
        _verify_distribution_audit(directory, record, report, policy_bytes, prices)
    return report, content


def _verify_distribution_audit(directory: Path, record: dict, report: dict,
                               policy_bytes: bytes, prices: pd.DataFrame | None) -> None:
    if report["reconciliation_version"] != RECONCILIATION_VERSION or prices is None:
        raise ValueError("Versión de contraste incompatible o precios no disponibles para verificarla")
    if any(report["checks"][name]["status"] != "not_evaluated" for name in ("prices", "adjustments")):
        raise ValueError("Un contraste de distribuciones no acredita precios ni ajustes")
    files = {name: (directory / name).read_bytes() for name in
             ("reference_manifest.json", "reference_dividends.parquet", "distribution_comparison.parquet")}
    if any(hashlib.sha256(data).hexdigest() != record["artifacts_sha256"][name] for name, data in files.items()):
        raise ValueError("SHA-256 incorrecto: los resultados del contraste han cambiado")
    reference_binding = report["reference"]
    reference, manifest_bytes = load_reference(reference_binding["directory"], policy_bytes)
    manifest = json.loads(manifest_bytes)
    if (files["reference_manifest.json"] != manifest_bytes
            or hashlib.sha256(manifest_bytes).hexdigest() != reference_binding["manifest_sha256"]
            or manifest["artifacts_sha256"]["original.xlsx"] != reference_binding["original_sha256"]
            or hashlib.sha256(files["reference_dividends.parquet"]).hexdigest() != reference_binding["normalized_sha256"]
            or manifest["artifacts_sha256"]["dividends.parquet"] != reference_binding["normalized_sha256"]):
        raise ValueError("El contraste no corresponde a la referencia conservada")
    config = tomllib.loads((directory / "config.toml").read_text())
    if (config["reference"] != {"provider": "ssga_dividends", "start": manifest["coverage"]["start"],
                                "end": manifest["coverage"]["end_exclusive"]}
            or config["reconciliation"] != {"absolute_tolerance_usd": ABSOLUTE_TOLERANCE_USD}):
        raise ValueError("La configuración del contraste no coincide con la referencia y el protocolo")
    check, details = reconcile_dividends(prices, reference, manifest["coverage"],
                                        report["interval"]["start"], report["interval"]["end_exclusive"],
                                        tolerance=ABSOLUTE_TOLERANCE_USD)
    if check != report["checks"]["dividends"]:
        raise ValueError("El estado del contraste no se reproduce con sus entradas")
    try:
        pd.testing.assert_frame_equal(pd.read_parquet(BytesIO(files["distribution_comparison.parquet"])), details, check_exact=True)
    except AssertionError as exc:
        raise ValueError("Los detalles del contraste no se reproducen") from exc
    if check["status"] == "failed" or record["audit_result"] != "partial":
        raise ValueError("El contraste contiene discrepancias sin resolver; revisa el informe antes de adjuntarlo")
