"""Consulta interactiva de ejecuciones y apertura local de sus archivos."""

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys


PAGE_SIZE = 8
MONTHLY_COMMANDS = {"prepare-shiller", "build-shiller-signals"}
TASKS = {
    "prepare-shiller": "Preparar datos de Shiller",
    "build-shiller-signals": "Generar señales de Shiller",
    "prepare-prices": "Preparar precios de SPY",
    "simulate-buy-and-hold": "Comprar y mantener SPY",
    "audit-prices": "Comprobar datos de SPY",
}
STATUSES = {"completed": "Terminada", "failed": "Fallida", "interrupted": "Interrumpida", "running": "En curso"}
CHECK_STATUSES = {"passed": "Superados", "failed": "Con discrepancias", "partial": "Parcial", "pending": "Pendiente"}


def display_time(value) -> str:
    """Fecha de la ejecución en el horario local del ordenador."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, AttributeError, TypeError):
        return "Fecha no disponible"


def _project_path(value, root: Path) -> Path | None:
    if not isinstance(value, (str, Path)) or not str(value):
        return None
    path = (root / value).resolve()
    return path if path.is_relative_to(root) and path.exists() else None


def _reveal(path: Path) -> None:
    """Abrir Finder solo al pedirlo; sin shell ni modificaciones de archivos."""
    if sys.platform != "darwin":
        print(f"La apertura en Finder requiere macOS. Ubicación: {path}")
        return
    command = ["open", str(path)] if path.is_dir() else ["open", "-R", str(path)]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=5)
        print("Carpeta abierta en Finder." if path.is_dir() else "Archivo seleccionado en Finder.")
    except (OSError, subprocess.SubprocessError):
        print(f"No se pudo mostrar en Finder. Ubicación: {path}")


def _actions(root: Path, directory: Path, record: dict) -> list[tuple[str, Path]]:
    """Ofrecer solo archivos locales existentes y con un papel explícito."""
    actions = []
    command = record.get("command", "prepare-prices")
    prepared = _project_path(record.get("prepared_dir"), root)
    table = None
    if prepared is not None and prepared.is_dir():
        for name in ("monthly.parquet", "prices.parquet"):
            table = _project_path(prepared / name, root)
            if table is not None and table.is_file():
                break
        else:
            table = None
    if command in {"prepare-shiller", "prepare-prices"}:
        primary = table
    else:
        key = {"build-shiller-signals": "signals_path", "simulate-buy-and-hold": "equity_path",
               "audit-prices": "audit_report_path"}.get(command)
        primary = _project_path(record.get(key), root) if key else None
    if primary is not None and primary.is_file():
        actions.append(("Mostrar resultado principal en Finder", primary))
    if table is not None and table != primary:
        actions.append(("Mostrar tabla de datos de entrada en Finder", table))
    summary = _project_path(directory / "summary.json", root)
    quality = _project_path(record.get("quality_report_path") or directory / "quality_report.json", root)
    if summary is not None:
        actions.append(("Mostrar resumen de resultados en Finder", summary))
    elif quality is not None:
        actions.append(("Mostrar informe de calidad en Finder", quality))
    snapshot = _project_path(record.get("snapshot_dir"), root)
    if snapshot is not None and snapshot.is_dir():
        for name in ("original.xls", "prices.parquet"):
            original = _project_path(snapshot / name, root)
            if original is not None and original.is_file():
                actions.append(("Mostrar archivo original en Finder", original))
                break
    actions.append(("Abrir carpeta de esta ejecución en Finder", directory))
    return actions


def _overview(directory: Path, record: dict) -> None:
    command = record.get("command", "prepare-prices")
    print(TASKS.get(command, command))
    print(f"Fecha local: {display_time(record.get('started_at_utc'))}")
    print(f"Estado de la tarea: {STATUSES.get(record.get('status'), record.get('status', 'Desconocido'))}")
    if record.get("audit_result"):
        print(f"Resultado de la comprobación: {CHECK_STATUSES.get(record['audit_result'], record['audit_result'])}")
    if isinstance(record.get("error"), dict):
        message = str(record["error"].get("message", "Error sin descripción"))
        print(f"Error: {(message.splitlines() or ['Error sin descripción'])[0][:180]}")
    for name in ("summary.json", "quality_report.json"):
        try:
            report = json.loads((directory / name).read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                continue
            first = report.get("target_start") or report.get("first_period") or report.get("first_session")
            last = report.get("target_end") or report.get("last_period") or report.get("last_session")
            if first and last:
                print(f"Periodo de los datos: {first} → {last}")
            if "rows" in report:
                print(f"Filas: {report['rows']}")
            if "both_rules_available" in report:
                print(f"Meses con ambas señales disponibles: {report['both_rules_available']}")
            if "status" in report:
                status = report["status"]
                print(f"Controles del informe: {CHECK_STATUSES.get(status, status)}")
            break
        except (OSError, ValueError, TypeError):
            continue


def _details(root: Path, directory: Path, record: dict, clear_screen) -> None:
    while True:
        clear_screen()
        _overview(directory, record)
        print()
        actions = _actions(root, directory, record)
        for number, (label, _) in enumerate(actions, 1):
            print(f"{number}. {label}")
        print("D. Ver identificador, rutas y detalles técnicos\n0. Volver al historial")
        answer = input("Acción: ").strip().lower()
        if answer == "0":
            return
        if answer == "d":
            clear_screen()
            print(f"Registro: {directory / 'run.json'}")
            print(json.dumps(record, indent=2, ensure_ascii=False))
            input("\nPulsa Intro para volver a la ejecución…")
        elif answer.isdecimal() and 1 <= int(answer) <= len(actions):
            _reveal(actions[int(answer) - 1][1])
            input("\nPulsa Intro para volver a la ejecución…")
        else:
            print("Selecciona una acción de la lista, D o 0.")
            input("Pulsa Intro para continuar…")


def browse_runs(config_path: Path, clear_screen) -> None:
    """Listar por páginas, seleccionar y consultar; nunca ejecutar cálculos."""
    root = config_path.resolve().parent.parent
    records, unreadable = [], 0
    for path in sorted((root / "outputs/runs").glob("*/run.json"), reverse=True):
        # No abrir ni seguir enlaces de directorios externos al proyecto.
        if not path.resolve().is_relative_to(root):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(record, dict) or not isinstance(record.get("status"), str)
                    or not isinstance(record.get("command", "prepare-prices"), str)):
                raise ValueError("Registro incompatible")
            records.append((path.parent, record))
        except (OSError, ValueError, TypeError):
            unreadable += 1
    monthly_only, page = True, 0
    while True:
        clear_screen()
        selected = [(path, record) for path, record in records
                    if not monthly_only or record.get("command") in MONTHLY_COMMANDS]
        pages = max(1, (len(selected) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, pages - 1)
        visible = selected[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        print(f"Historial · {'Shiller' if monthly_only else 'Todas las tareas'} · Más recientes primero")
        print(f"Página {page + 1} de {pages} | {len(selected)} ejecuciones")
        if unreadable:
            print(f"Registros ilegibles omitidos: {unreadable}")
        if not visible:
            print("No hay ejecuciones para este filtro.")
        for number, (_, record) in enumerate(visible, 1):
            command = record.get("command", "prepare-prices")
            status = STATUSES.get(record.get("status"), record.get("status"))
            print(f"{number}. {display_time(record.get('started_at_utc'))} | {TASKS.get(command, command)} | {status}")
        print("\nEscribe el número de una ejecución para consultar sus resultados.")
        if page + 1 < pages:
            print("N. Página siguiente")
        if page:
            print("P. Página anterior")
        print("T. Ver todas las tareas, incluidas SPY" if monthly_only else "T. Ver solo Shiller")
        print("0. Volver al menú principal")
        answer = input("Selección: ").strip().lower()
        if answer == "0":
            return
        if answer == "t":
            monthly_only, page = not monthly_only, 0
        elif answer == "n" and page + 1 < pages:
            page += 1
        elif answer == "p" and page:
            page -= 1
        elif answer.isdecimal() and 1 <= int(answer) <= len(visible):
            directory, record = visible[int(answer) - 1]
            _details(root, directory, record, clear_screen)
        else:
            print("Selecciona una opción de la lista.")
            input("Pulsa Intro para continuar…")
