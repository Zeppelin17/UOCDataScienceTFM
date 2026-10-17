"""Menú local que reutiliza el flujo de datos existente."""

import json
import os
import sys
from pathlib import Path
import tomllib

from tfm.pipeline import PipelineError, load_buy_and_hold_config, run_buy_and_hold, run_prepare_prices


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
    for warning in report.get("warnings", []):
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
    for warning in summary["warnings"]:
        print(f"Nota: {warning}")
    print(f"Trayectoria: {run_dir / 'equity.parquet'}")
    print(f"Resumen: {run_dir / 'summary.json'}")
    print(f"Registro: {run_dir / 'run.json'}")


def _select_prepared_prices(settings: dict) -> Path | None:
    items = []
    for path in sorted(settings["processed_root"].glob("prices/*/manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest["status"] != "passed" or manifest["source_manifest"]["instrument"] != "SPY":
                continue
            report = json.loads((path.parent / "quality_report.json").read_text(encoding="utf-8"))
            first, last = report["first_session"][:10], report["last_session"][:10]
            simulation = settings["simulation"]
            if (report["status"] != "passed" or first > simulation["start"]
                    or last < simulation["end"] or last > settings["development_end"]):
                continue
            items.append(path.parent)
            print(f"{len(items)}. SPY | {first} → {last} | {report['rows']} sesiones | {path.parent.name}")
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer la preparación: {path.parent}")
    if not items:
        print("No hay precios preparados compatibles con el intervalo. Prepara los datos o revisa configs/buy_and_hold.toml.")
        return None
    while True:
        answer = input(f"Número de preparación (1–{len(items)}; 0 para volver): ").strip()
        if answer == "0":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print("Selecciona un número de la lista; 0 para volver.")


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
                  "0. Salir")
            option = input("Opción del menú (0–6): ").strip()
            if option == "0":
                return 0
            if option not in {"1", "2", "3", "4", "5", "6"}:
                pause = True
                print("Escribe un número del 0 al 6.")
                continue
            pause = True
            _clear_screen()
            if option == "3":
                _show_runs(config_path)
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
                    run_dir = run_buy_and_hold(simulation_path, prepared)
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
