"""Estados independientes de calidad; no confundir cobertura y exactitud."""


CHECK_LABELS = {
    "calendar": "Calendario",
    "prices": "Contraste independiente de precios",
    "dividends": "Contraste independiente de dividendos",
    "adjustments": "Contraste de ajustes de rentabilidad total",
}
LEGACY_WARNING = "La integridad del calendario bursátil y el contraste con otra fuente siguen pendientes"


def pending_checks() -> dict:
    return {key: {"status": "not_evaluated"} for key in CHECK_LABELS}


def quality_messages(checks: dict) -> list[str]:
    states = {"passed": "superado", "failed": "discrepancias", "partial": "parcial", "not_evaluated": "pendiente"}
    messages = []
    for key, label in CHECK_LABELS.items():
        check = checks.get(key, {"status": "not_evaluated"})
        state = states.get(check["status"], "estado desconocido")
        detail = ""
        if key == "calendar" and check["status"] in {"passed", "failed"}:
            detail = f" ({check['observed_sessions']} observadas / {check['expected_sessions']} esperadas, {check['calendar_name']})"
        messages.append(f"{label}: {state}{detail}.")
    return messages


def other_warnings(report: dict) -> list[str]:
    """Los informes antiguos se conservan; su nota combinada se muestra por estados."""
    return list(dict.fromkeys(w for w in report.get("warnings", []) if w != LEGACY_WARNING))
