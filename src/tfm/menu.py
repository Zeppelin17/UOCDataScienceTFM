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
    import_ssga_reference, load_reconciliation_config,
    load_shiller_config, run_prepare_shiller,
    load_shiller_signals_config, run_shiller_signals,
)
from tfm.preparation.quality import other_warnings, pending_checks, quality_messages
from tfm.run_browser import browse_runs, display_time


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
    browse_runs(config_path, _clear_screen)


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


def show_shiller_result(run_dir: Path) -> None:
    report = json.loads((run_dir / "quality_report.json").read_bytes())
    record = json.loads((run_dir / "run.json").read_bytes())
    interval = report["interval"]
    print("Preparación de la historia mensual de Shiller terminada.")
    print(f"Periodo preparado: {report['first_period']} → {report['last_period']} | Meses: {report['rows']}")
    print(f"Historia previa: {interval['history_start']} → 1926-12 | {report['history_rows']} meses")
    print(f"Desarrollo: {interval['development_start']} → {interval['development_end']} | {report['development_rows']} meses")
    print("Evaluación desde 1990: importes excluidos de la tabla preparada.")
    print("Controles de estructura y cobertura mensual: superados.")
    for warning in report["warnings"]:
        print(f"Nota: {warning}")
    print(f"Tabla mensual: {record['prepared_dir']}/monthly.parquet")
    print(f"Original archivado: {record['snapshot_dir']}")
    print(f"Registro: {run_dir / 'run.json'}")


def show_shiller_signals_result(run_dir: Path) -> None:
    summary = json.loads((run_dir / "summary.json").read_bytes())
    print("Señales mensuales de Shiller generadas; diagnóstico sin simulación de rentabilidades.")
    print(f"Meses objetivo: {summary['target_start']} → {summary['target_end']} | {summary['rows']} meses")
    print(f"Historia suficiente para ambas reglas: {summary['both_rules_available']} meses")
    print(f"Periodo común: {summary['first_common_target']} → {summary['last_common_target']}")
    print("Señales: +1 largo, -1 corto, 0 efectivo; campo vacío significa historia insuficiente.")
    for name, label in (("momentum", "Momentum"), ("reversal", "Reversión")):
        if summary[f"missing_{name}_targets"]:
            print(f"{label}, meses sin historia suficiente: {', '.join(summary[f'missing_{name}_targets'])}")
    for warning in summary["warnings"]:
        print(f"Nota: {warning}")
    print(f"Tabla para consultar: {run_dir / 'signals.csv'}")
    print(f"Tabla Parquet: {run_dir / 'signals.parquet'}")
    print(f"Resumen: {run_dir / 'summary.json'}")
    print(f"Registro: {run_dir / 'run.json'}")


def _select_shiller_preparation(settings: dict) -> Path | None:
    items = []
    for path in sorted(settings["processed_root"].glob("shiller_monthly/*/manifest.json")):
        try:
            manifest = json.loads(path.read_bytes())
            interval = manifest["interval"]
            if (manifest["kind"] != "shiller_monthly_observations" or manifest["status"] != "passed"
                    or manifest["instrument"] != "SHILLER_SP_COMPOSITE"
                    or interval["development_start"] != settings["development_start"][:7]
                    or interval["development_end"] != settings["development_end"][:7]):
                continue
            items.append(path.parent)
            print(f"{len(items)}. Preparada: {display_time(manifest.get('created_at_utc'))} | {interval['history_start']} → {interval['development_end']}")
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer la preparación: {path.parent}")
    if not items:
        print("No hay preparaciones mensuales compatibles. Prepara Shiller con la opción 9.")
        return None
    while True:
        answer = input(f"Número de preparación (1–{len(items)}; 0 para volver): ").strip()
        if answer == "0":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print("Selecciona un número de la lista; no se elige automáticamente la última preparación.")


def _select_shiller_input(settings: dict) -> dict | None:
    items = []
    for path in sorted(settings["raw_root"].glob("shiller/SHILLER_SP_COMPOSITE/*/manifest.json")):
        try:
            manifest = json.loads(path.read_bytes())
            if (manifest["schema_version"] != 1 or manifest["provider"] != "shiller"
                    or manifest["instrument"] != "SHILLER_SP_COMPOSITE" or manifest["status"] != "archived"):
                continue
            items.append(path.parent)
            print(f"{len(items)}. Original archivado: {display_time(manifest.get('archived_at_utc'))}")
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer el original: {path.parent}")
    print("D. Descargar una nueva copia del Excel oficial")
    print("F. Importar un Excel XLS original que ya tienes en el ordenador")
    while True:
        answer = input("Número de original, D para descargar, F para importar o 0 para volver: ").strip()
        if answer == "0":
            return None
        if answer.lower() == "d":
            return {}
        if answer.lower() == "f":
            filename = input("Ruta del XLS original (Intro o 0 para volver): ").strip()
            return None if filename in {"", "0"} else {"file_path": Path(filename).expanduser()}
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return {"snapshot_dir": items[int(answer) - 1]}
        print("Selecciona un original de la lista, D, F o 0; no se elige automáticamente.")


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
    extended = report["schema_version"] == 2
    print("Auditoría ejecutada. Alcance: " + ("calendario y distribuciones monetarias." if extended else "calendario de sesiones; no contraste de precios."))
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
    if extended:
        print("Precios de mercado y ajustes de rentabilidad total permanecen pendientes.")
        print(f"Comparaciones por evento: {run_dir / 'distribution_comparison.parquet'}")
        import pandas as pd
        details = pd.read_parquet(run_dir / "distribution_comparison.parquet")
        differences = details.loc[details["result"].ne("within_tolerance")]
        for row in differences.head(10).itertuples():
            print(f"  {row.observed_at.date()} | Yahoo: {row.yahoo_distribution:.6f} USD | SSGA: {row.ssga_distribution:.6f} USD | {row.result}")
        if len(differences) > 10:
            print("La lista completa está en la tabla de comparaciones.")
        print("Una discrepancia no determina cuál de las fuentes es correcta; no se han reparado los datos.")
    return not any(check["status"] == "failed" for check in report["checks"].values())


def _select_reference(settings: dict, config_path: Path) -> Path | None:
    items = []
    for path in sorted(settings["raw_root"].glob("ssga/SPY/*/manifest.json")):
        try:
            manifest = json.loads(path.read_bytes())
            coverage = manifest["coverage"]
            if manifest["status"] != "completed":
                continue
            items.append(path.parent)
            print(f"{len(items)}. SSGA | {coverage['start']} → {coverage['end_exclusive']} (fin exclusivo) | {manifest['rows']} eventos | {path.parent.name}")
        except (OSError, ValueError, KeyError, TypeError):
            print(f"No se pudo leer la referencia: {path.parent}")
    print("I. Importar otro Excel oficial de distribuciones de State Street")
    while True:
        answer = input("Número de referencia, I para importar o 0 para volver: ").strip()
        if answer == "0":
            return None
        if answer.lower() == "i":
            print("Descarga 'SPDR Historical Distributions XLSX' desde:")
            print("https://www.ssga.com/us/en/intermediary/resources/documents/etf-dividend-distributions")
            filename = input("Ruta del Excel (Intro o 0 para volver): ").strip()
            if filename in {"", "0"}:
                return None
            directory = import_ssga_reference(config_path, Path(filename).expanduser())
            print(f"Referencia importada: {directory}")
            return directory
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print("Selecciona una referencia de la lista, I o 0.")


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
            print(f"{len(items)}. Auditoría {path.parent.name} | calendario: {report['checks']['calendar']['status']} | dividendos: {report['checks']['dividends']['status']}")
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
            print(f"Configuración en uso: {config_path} (exploración anterior de SPY)")
            print("Estudio principal: historia mensual; desarrollo 1927–1989, evaluación desde 1990.")
            print("¿Qué quieres hacer?\n"
                  "1. Descargar y preparar precios de SPY (exploración anterior)\n"
                  "2. Preparar una descarga de SPY existente (exploración anterior)\n"
                  "3. Consultar ejecuciones anteriores\n"
                  "4. Ver la configuración de SPY\n"
                  "5. Cambiar configuración de SPY\n"
                  "6. Simular comprar y mantener SPY (exploración anterior)\n"
                  "7. Auditar calendario de SPY (exploración anterior)\n"
                  "8. Contrastar dividendos de SPY (exploración anterior)\n"
                  "9. Preparar historia mensual de Shiller (estudio principal)\n"
                  "10. Generar señales mensuales de Shiller (sin simular rentabilidades)\n"
                  "0. Salir")
            option = input("Opción del menú (0–10): ").strip()
            if option == "0":
                return 0
            if option not in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}:
                pause = True
                print("Escribe un número del 0 al 10.")
                continue
            pause = True
            _clear_screen()
            if option == "10":
                signals_path = config_path.resolve().parent / "shiller_signals.toml"
                settings = load_shiller_signals_config(signals_path)
                print(f"Configuración de señales: {signals_path}")
                print("Base: promedios mensuales de Shiller. Momentum no positivo: efectivo.")
                print("Señales para 1927–1989; sin descargas ni simulación de operaciones.")
                prepared = _select_shiller_preparation(settings)
                if prepared is not None:
                    run_dir = run_shiller_signals(signals_path, prepared)
                    _clear_screen()
                    show_shiller_signals_result(run_dir)
                continue
            if option == "9":
                monthly_path = config_path.resolve().parent / "shiller_monthly.toml"
                settings = load_shiller_config(monthly_path)
                print(f"Configuración del estudio mensual: {monthly_path}")
                print(f"Historia desde {settings['history_start']} | Desarrollo 1927–1989 | Evaluación desde 1990 excluida")
                print("P es un promedio mensual y D un importe anualizado interpolado; todavía no se simulan estrategias.")
                origin = _select_shiller_input(settings)
                if origin is not None:
                    run_dir = run_prepare_shiller(monthly_path, **origin)
                    _clear_screen()
                    show_shiller_result(run_dir)
                continue
            if option == "3":
                pause = False
                _show_runs(config_path)
                continue
            if option == "8":
                audit_path = config_path.resolve().parent / "reconciliation.toml"
                settings = load_reconciliation_config(audit_path)
                print(f"Configuración de contraste: {audit_path}")
                print(f"Desarrollo hasta {settings['development_end']}; sin contraste de cierres ni ajustes.")
                prepared = _select_prepared_prices(settings)
                if prepared is not None:
                    reference = _select_reference(settings, audit_path)
                    if reference is not None:
                        run_dir = run_audit_prices(audit_path, prepared, reference)
                        _clear_screen()
                        show_audit_result(run_dir)
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
