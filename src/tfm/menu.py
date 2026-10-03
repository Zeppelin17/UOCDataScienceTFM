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
            label = f"{manifest['instrument']} {parameters['start']} → {parameters['end']} | {manifest['snapshot_id']}"
            items.append((manifest_path.parent, label))
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer: {manifest_path}")
    if not items:
        print("No hay descargas disponibles.")
        return None
    for number, (_, label) in enumerate(items, 1):
        print(f"{number}. {label}")
    while True:
        answer = input("Número de descarga (0 para volver): ").strip()
        if answer == "0":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1][0]
        print("Selecciona un número de la lista.")


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


def interactive_menu() -> int:
    """Elegir tareas; Ctrl+C cancela la acción y Ctrl+D sale del menú."""
    config_path = Path("configs/data.toml")
    while True:
        try:
            print("\n¿Qué quieres hacer?\n"
                  "1. Descargar y preparar precios\n"
                  "2. Preparar una descarga existente\n"
                  "3. Consultar ejecuciones anteriores\n"
                  "4. Ver la configuración actual\n"
                  "0. Salir")
            option = input("Opción: ").strip()
            if option == "0":
                return 0
            if option not in {"1", "2", "3", "4"}:
                print("Selecciona una opción de la lista.")
                continue
            if option == "3":
                _show_runs(config_path)
                continue
            selected = input(f"Configuración [{config_path}] (0 para volver): ").strip()
            if selected == "0":
                continue
            candidate = Path(selected) if selected else config_path
            config = _configuration(candidate)
            _show_configuration(candidate, config)
            config_path = candidate
            if option == "4":
                print(json.dumps(config, indent=2, ensure_ascii=False))
                continue
            snapshot = None
            if option == "2":
                snapshot = _snapshots(config_path, config)
                if snapshot is None:
                    continue
            run_dir = run_prepare_prices(config_path, snapshot)
            record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            print(f"Ejecución: {run_dir}")
            print(f"Precios preparados: {record['prepared_dir']}")
        except KeyboardInterrupt:
            print("\nAcción cancelada; vuelves al menú.")
        except EOFError:
            print("\nSaliendo.")
            return 0
        except (PipelineError, OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Error: {exc}")
