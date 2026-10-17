"""Menú local que reutiliza el flujo de datos existente."""

import hashlib
import json
import os
import sys
from pathlib import Path
import tomllib

from tfm.pipeline import (
    PipelineError, load_audit_config, load_buy_and_hold_config,
    run_audit_prices, run_buy_and_hold, run_prepare_prices,
)
from tfm.preparation.quality import other_warnings, pending_checks, quality_messages


def _clear_screen() -> None:
    """Limpiar solo la pantalla de una terminal compatible."""
    if sys.stdout.isatty() and os.environ.get("TERM") != "dumb":
        print("\033[2J\033[H", end="", flush=True)


def _pause() -> bool:
    """Conservar la pantalla hasta Intro; devolver False si se cierra la entrada."""
    try:
        input("\nPulsa Intro para volver al menú…")
    except KeyboardInterrupt:
        print()
    except EOFError:
        return False
    return True


def _configuration(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _show_configuration(path: Path, config: dict) -> None:
    market = config["market"]
    print(f"Configuración: {path.resolve()}")
    print(f"{market['instrument']} / {market['provider']} / {market['frequency']}")
    print(f"Periodo: {market['start']} → {market['end']} (fin exclusivo)")


def _snapshots(config_path: Path, config: dict) -> Path | None:
    raw = Path(config["storage"]["raw"])
    raw = config_path.resolve().parent.parent / raw
    items = []
    for manifest_path in sorted(raw.glob("yahoo/SPY/*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            parameters = manifest["parameters"]
            first = manifest.get("first_session", parameters["start"])[:10]
            last = manifest.get("last_session")
            period = f"{first} → {last[:10]}" if last else f"{first} → {parameters['end']} (fin exclusivo)"
            downloaded = manifest.get("completed_at_utc", manifest["snapshot_id"])
            label = f"{manifest['instrument']} | {period} | descarga: {downloaded}"
            if "rows" in manifest:
                label += f" | {manifest['rows']} sesiones"
            items.append((manifest_path.parent, label))
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer: {manifest_path}")
    if not items:
        print("No hay descargas disponibles.")
        return None
    for number, (_, label) in enumerate(items, 1):
        print(f"{number}. {label}")
    choices = " o ".join(str(number) for number in range(1, len(items) + 1)) if len(items) <= 3 else f"un número del 1 al {len(items)}"
    prompt = f"Escribe {choices} para seleccionar una descarga; 0 para volver: "
    while True:
        answer = input(prompt).strip()
        if answer == "0":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1][0]
        print(f"No se ha seleccionado ninguna descarga. {prompt}")


def _show_runs(config_path: Path) -> None:
    runs = config_path.resolve().parent.parent / "outputs/runs"
    records = sorted(runs.glob("*/run.json"))
    if not records:
        print("No hay ejecuciones registradas.")
    for path in records:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            print(f"{record['run_id']} | {record.get('command', 'prepare-prices')} | {record['status']} | {record['stage']}")
            print(f"  Registro: {path}")
            if record.get("audit_report_path"):
                print(f"  Resultado de calendario: {record['audit_result']}")
                print(f"  Auditoría: {record['audit_report_path']}")
            if record.get("equity_path"):
                print(f"  Resultado: {record['equity_path']}")
                print(f"  Resumen: {record['summary_path']}")
            elif record.get("prepared_dir"):
                print(f"  Resultado: {record['prepared_dir']}")
            if record.get("quality_report_path"):
                print(f"  Informe: {record['quality_report_path']}")
            if record.get("error"):
                print(f"  Error: {record['error']['message']}")
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer: {path}")


def _show_result(run_dir: Path) -> None:
    report = json.loads((run_dir / "quality_report.json").read_text(encoding="utf-8"))
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print("\nPreparación terminada.")
    print(f"Sesiones: {report['rows']:,}".replace(",", "."))
    print(f"Periodo: {report['first_session'][:10]} → {report['last_session'][:10]}")
    print(f"Controles de calidad: {'superados' if report['status'] == 'passed' else 'no superados'}")
    for message in quality_messages(report.get("checks", pending_checks())):
        print(message)
    for warning in other_warnings(report):
        print(f"Pendiente: {warning}")
    print(f"Precios preparados: {record['prepared_dir']}")
    print(f"Registro de ejecución: {run_dir / 'run.json'}")


def show_simulation_result(run_dir: Path) -> None:
    """Resumen común para menú y comando explícito."""
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    print("Simulación de comprar y mantener terminada.")
    print(f"Periodo efectivo: {summary['first_session']} → {summary['last_session']}")
    print(f"Entrada al cierre: {summary['entry_at']} | Sesiones: {summary['sessions']}")
    print(f"Rentabilidad bruta: {summary['gross_total_return']:.2%}")
    print(f"Rentabilidad neta: {summary['net_total_return']:.2%}")
    print(f"Capital final neto (inicial = 1): {summary['final_net_capital']:.6f}")
    print(f"Costes en unidades de capital: {summary['total_cost_amount']:.6f}")
    print(f"Rotación acumulada: {summary['total_turnover']:.2f}")
    print(f"Caída máxima neta: {summary['max_drawdown']:.2%}")
    for message in quality_messages(summary.get("checks", pending_checks())):
        print(message)
    for warning in summary["warnings"]:
        print(f"Nota: {warning}")
    print(f"Trayectoria: {run_dir / 'equity.parquet'}")
    print(f"Resumen: {run_dir / 'summary.json'}")
    print(f"Registro: {run_dir / 'run.json'}")


def show_audit_result(run_dir: Path) -> bool:
    report = json.loads((run_dir / "audit_report.json").read_text(encoding="utf-8"))
    print("Auditoría ejecutada. Alcance: calendario de sesiones; no contraste de precios.")
    interval = report["interval"]
    print(f"Intervalo completo solicitado: {interval['start']} → {interval['end_exclusive']} (fin exclusivo)")
    for message in quality_messages(report["checks"]):
        print(message)
    calendar = report["checks"]["calendar"]
    for key, label in (("missing_sessions", "Sesiones ausentes"), ("unexpected_sessions", "Fechas inesperadas")):
        if calendar[key]:
            print(f"{label}: {', '.join(calendar[key][:10])}")
            if len(calendar[key]) > 10:
                print("La lista completa está en el informe.")
    print(f"Versión del calendario: {calendar['library_version']} | Sesiones reducidas: {calendar['early_close_sessions']}")
    print("XNYS es la referencia de sesiones diarias US; no certifica precios ni el horario intradía de SPY.")
    print(f"Informe: {run_dir / 'audit_report.json'}")
    print(f"Sesiones esperadas: {run_dir / 'calendar_sessions.parquet'}")
    print(f"Registro: {run_dir / 'run.json'}")
    return calendar["status"] == "passed"


def _select_prepared_prices(settings: dict) -> Path | None:
    items = []
    for path in sorted(settings["processed_root"].glob("prices/*/manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest["status"] != "passed" or manifest["source_manifest"]["instrument"] != "SPY":
                continue
            report = json.loads((path.parent / "quality_report.json").read_text(encoding="utf-8"))
            first, last = report["first_session"][:10], report["last_session"][:10]
            simulation = settings.get("simulation")
            if report["status"] != "passed" or last > settings["development_end"]:
                continue
            if simulation is not None and (first > simulation["start"] or last < simulation["end"]):
                continue
            items.append(path.parent)
            print(f"{len(items)}. SPY | {first} → {last} | {report['rows']} sesiones | {path.parent.name}")
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer la preparación: {path.parent}")
    if not items:
        print("No hay precios preparados compatibles. Prepara los datos o revisa el intervalo de la configuración.")
        return None
    while True:
        answer = input(f"Número de preparación (1–{len(items)}; 0 para volver): ").strip()
        if answer == "0":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print("Selecciona un número de la lista; 0 para volver.")


def _select_audit(prepared: Path, runs_root: Path) -> Path | None:
    manifest_bytes = (prepared / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    items = []
    for path in sorted(runs_root.glob("*/run.json")):
        try:
            record = json.loads(path.read_bytes())
            if record.get("command") != "audit-prices" or record["status"] != "completed":
                continue
            report = json.loads((path.parent / "audit_report.json").read_bytes())
            if (report["binding"]["prices_sha256"] != manifest["sha256"]
                    or report["binding"]["prepared_manifest_sha256"] != manifest_hash):
                continue
            items.append(path.parent)
            print(f"{len(items)}. Auditoría {path.parent.name} | calendario: {record['audit_result']}")
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not items:
        print("No hay auditorías disponibles para estos precios; simulación exploratoria con calendario pendiente.")
        return None
    while True:
        answer = input(f"Auditoría (1–{len(items)}; 0 para simular SIN auditoría): ").strip()
        if answer == "0":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print("Selecciona una auditoría de la lista o 0; no se elige automáticamente.")


def interactive_menu() -> int:
    """Elegir tareas; Ctrl+C cancela la acción y Ctrl+D sale del menú."""
    config_path = Path("configs/data.toml")
    stop = False
    while not stop:
        pause = False
        try:
            _clear_screen()
            print(f"Configuración en uso: {config_path}")
            print("¿Qué quieres hacer?\n"
                  "1. Descargar y preparar precios\n"
                  "2. Preparar una descarga existente\n"
                  "3. Consultar ejecuciones anteriores\n"
                  "4. Ver la configuración actual\n"
                  "5. Cambiar configuración\n"
                  "6. Simular comprar y mantener\n"
                  "7. Auditar calendario de precios preparados\n"
                  "0. Salir")
            option = input("Opción del menú (0–7): ").strip()
            if option == "0":
                return 0
            if option not in {"1", "2", "3", "4", "5", "6", "7"}:
                pause = True
                print("Escribe un número del 0 al 7.")
                continue
            pause = True
            _clear_screen()
            if option == "3":
                _show_runs(config_path)
                continue
            if option == "7":
                audit_path = config_path.resolve().parent / "audit.toml"
                settings = load_audit_config(audit_path)
                print(f"Configuración de auditoría: {audit_path}")
                print(f"Calendario de referencia: {settings['calendar']} | Desarrollo hasta {settings['development_end']}")
                prepared = _select_prepared_prices(settings)
                if prepared is not None:
                    run_dir = run_audit_prices(audit_path, prepared)
                    _clear_screen()
                    show_audit_result(run_dir)
                continue
            if option == "6":
                simulation_path = config_path.resolve().parent / "buy_and_hold.toml"
                settings = load_buy_and_hold_config(simulation_path)
                simulation = settings["simulation"]
                print(f"Configuración independiente de simulación: {simulation_path}")
                print(f"SPY | {simulation['start']} → {simulation['end']} (fechas inclusivas)")
                print(f"Coste por unidad negociada: {simulation['cost_bps']} puntos básicos (escenario ilustrativo)")
                print(f"Desarrollo hasta: {settings['development_end']} | Política: {settings['policy_path']}")
                prepared = _select_prepared_prices(settings)
                if prepared is not None:
                    audit = _select_audit(prepared, simulation_path.parent.parent / "outputs/runs")
                    run_dir = run_buy_and_hold(simulation_path, prepared, audit)
                    _clear_screen()
                    show_simulation_result(run_dir)
                continue
            if option == "5":
                selected = input("Ruta del archivo TOML (Intro o 0 para volver sin cambiar): ").strip()
                if selected in {"", "0"}:
                    pause = False
                    continue
                candidate = Path(selected)
                config = _configuration(candidate)
                _show_configuration(candidate, config)
                # Comprobar las rutas necesarias antes de activar la configuración.
                for key in ("raw", "processed"):
                    Path(config["storage"][key])
                config_path = candidate
                print("Configuración cambiada para esta sesión del menú.")
                continue
            config = _configuration(config_path)
            _show_configuration(config_path, config)
            if option == "4":
                print(json.dumps(config, indent=2, ensure_ascii=False))
                continue
            snapshot = None
            if option == "2":
                snapshot = _snapshots(config_path, config)
                if snapshot is None:
                    continue
            else:
                print("Descargando una nueva copia y preparando los precios…")
            run_dir = run_prepare_prices(config_path, snapshot)
            _clear_screen()
            _show_result(run_dir)
        except KeyboardInterrupt:
            pause = True
            print("\nAcción cancelada; vuelves al menú.")
        except EOFError:
            pause = False
            print("\nSaliendo.")
            return 0
        except (PipelineError, OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Error: {exc}")
        finally:
            stop = pause and not _pause()
    return 0
