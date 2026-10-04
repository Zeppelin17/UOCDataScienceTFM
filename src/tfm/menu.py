"""Menú local que reutiliza el flujo de datos existente."""

import json
from pathlib import Path
import tomllib

from tfm.pipeline import PipelineError, run_prepare_prices


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
            print(f"{record['run_id']} | {record['status']} | {record['stage']}")
            print(f"  Registro: {path}")
            if record.get("prepared_dir"):
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


def interactive_menu() -> int:
    """Elegir tareas; Ctrl+C cancela la acción y Ctrl+D sale del menú."""
    config_path = Path("configs/data.toml")
    while True:
        try:
            print(f"\nConfiguración en uso: {config_path}")
            print("¿Qué quieres hacer?\n"
                  "1. Descargar y preparar precios\n"
                  "2. Preparar una descarga existente\n"
                  "3. Consultar ejecuciones anteriores\n"
                  "4. Ver la configuración actual\n"
                  "5. Cambiar configuración\n"
                  "0. Salir")
            option = input("Opción del menú (0–5): ").strip()
            if option == "0":
                return 0
            if option not in {"1", "2", "3", "4", "5"}:
                print("Escribe un número del 0 al 5.")
                continue
            if option == "3":
                _show_runs(config_path)
                continue
            if option == "5":
                selected = input("Ruta del archivo TOML (Intro o 0 para volver sin cambiar): ").strip()
                if selected in {"", "0"}:
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
            _show_result(run_dir)
        except KeyboardInterrupt:
            print("\nAcción cancelada; vuelves al menú.")
        except EOFError:
            print("\nSaliendo.")
            return 0
        except (PipelineError, OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Error: {exc}")
