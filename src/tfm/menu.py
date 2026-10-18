"""Recorridos guiados del TFM: fuente, tarea, resultado y siguiente paso."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys

from tfm.config import DEFAULT_CONFIG, load_config
from tfm.data import prepare_shiller_data, prepare_spy_data, calculate_signals, load_monthly, read_result
from tfm.sources.prices import DownloadError
# Compatibilidad de los comandos anteriores hasta el tercer incremento.
from tfm.preparation.quality import other_warnings, pending_checks, quality_messages


RESULTS = {
    "shiller_monthly": ("Datos mensuales de Shiller", "1. Preparar datos de Shiller"),
    "shiller_signals": ("Señales de momentum y reversión", "2. Calcular señales"),
    "spy_prices": ("Datos diarios del ETF SPY", "4. Trabajar con datos de SPY"),
}


def _clear_screen() -> None:
    if sys.stdout.isatty() and os.environ.get("TERM") != "dumb":
        print("\033[2J\033[H", end="", flush=True)


def _pause() -> bool:
    try:
        input("\nPulsa Intro para volver…")
    except KeyboardInterrupt:
        print()
    except EOFError:
        return False
    return True


def _choice(prompt: str, choices: set[str]) -> str:
    while True:
        answer = input(prompt).strip()
        if answer in choices:
            return answer
        print("Selecciona uno de los números mostrados; 0 permite volver.")


def _history(settings: dict, source: str) -> list[Path]:
    pattern = ("shiller/SHILLER_SP_COMPOSITE/*/original.xls" if source == "shiller"
               else "yahoo/SPY/*/prices.parquet")
    return sorted(p for p in (settings["root"] / "data/raw").glob(pattern) if p.is_file())


def _select_history(items: list[Path], source: str) -> Path | None:
    print(f"\nOriginales anteriores de {'Shiller' if source == 'shiller' else 'SPY'}")
    print("Selecciona la copia que quieras reutilizar. El archivo anterior se conservará.")
    for number, path in enumerate(items, 1):
        try:
            record = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
            stamp = record.get("archived_at_utc") or record.get("completed_at_utc")
            date = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M:%S")
        except (OSError, ValueError, TypeError, AttributeError):
            date = "fecha no registrada"
        print(f"{number}. Original guardado: {date}")
    print("0. Volver sin preparar datos")
    answer = _choice("Número de original: ", {"0", *(str(i) for i in range(1, len(items) + 1))})
    return None if answer == "0" else items[int(answer) - 1]


def _select_input(settings: dict, source: str) -> tuple[bool, Path | None]:
    raw = settings["root"] / "data/raw" / ("shiller.xls" if source == "shiller" else "spy.parquet")
    if raw.exists():
        print(f"Origen: original de trabajo guardado en data/raw/{raw.name}.")
        print("Se reutilizará sin descargar ni sustituir el original.")
        return True, None
    print("Todavía no hay un original de trabajo para esta fuente.")
    items = _history(settings, source)
    print("1. Descargar de la fuente configurada")
    print("2. Importar un archivo de mi ordenador")
    if items:
        print(f"3. Reutilizar un original de la etapa anterior ({len(items)} disponibles)")
    print("0. Volver sin preparar datos")
    answer = _choice("¿De dónde obtenemos los datos? ", {"0", "1", "2"} | ({"3"} if items else set()))
    if answer == "0":
        return False, None
    if answer == "1":
        print("Origen: descarga del Excel oficial de Shiller." if source == "shiller"
              else "Origen: Yahoo Finance mediante yfinance.")
        return True, None
    if answer == "3":
        selected = _select_history(items, source)
        return selected is not None, selected
    print("Pega la ruta del XLS original de Shiller." if source == "shiller" else
          "Pega la ruta del Parquet original descargado de Yahoo, con sus columnas originales.")
    while True:
        text = input("Ruta del archivo (0 para volver): ").strip().strip("\"'")
        if text == "0":
            return False, None
        path = Path(text).expanduser()
        if text and path.is_file():
            print(f"Origen: {path}")
            return True, path
        print("No se encuentra ese archivo. Revisa la ruta o escribe 0 para volver.")


def show_result(name: str, summary: dict) -> None:
    print(f"\n{RESULTS[name][0]}")
    if name == "shiller_monthly":
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['rows']} meses")
        print(f"Historia previa: {summary['history_rows']} meses | Desarrollo: {summary['development_rows']} meses")
        print("Sin meses ausentes ni duplicados; valores numéricos dentro de las condiciones exigidas.")
        print("P es un precio medio mensual; D es anualizado e interpolado, no un pago mensual observado.")
        print("Siguiente paso: opción 2 para calcular señales. La simulación sigue pendiente de definir con el tutor.")
    elif name == "shiller_signals":
        print(f"Meses objetivo: {summary['target_start']} → {summary['target_end']} | {summary['rows']} meses")
        print(f"Meses con ambas señales disponibles: {summary['both_rules_available']}")
        print("+1: posición que se beneficiaría de una subida; -1: de una bajada; 0: efectivo.")
        print("Una señal vacía significa historia insuficiente, no una decisión de permanecer fuera.")
        for rule, label in (("momentum", "Momentum"), ("reversal", "Reversión")):
            if summary[f"missing_{rule}_targets"]:
                print(f"{label}, sin historia suficiente: {', '.join(summary[f'missing_{rule}_targets'])}")
        print("Señales sobre promedios mensuales, sin simulación de rentabilidades ni entrenamiento de modelos.")
        print("Siguiente paso: consulta las señales en la opción 3. La simulación sigue pendiente de definir con el tutor.")
    else:
        print(f"Periodo: {summary['first_session'][:10]} → {summary['last_session'][:10]} | {summary['rows']} sesiones")
        print("Controles estructurales superados; calendario, ajustes y exactitud financiera no certificados.")
        print("SPY se mantiene separado de Shiller; su utilización definitiva en el estudio sigue pendiente.")
        print("Siguiente paso: consulta la tabla en la opción 3. No se han calculado señales ni rentabilidades de SPY.")
    print(f"Archivo: data/processed/{Path(summary['path']).name}")


def _prepare(config: Path, settings: dict, source: str) -> bool:
    if source == "shiller":
        print("Preparar datos de Shiller — estudio mensual")
        print(f"Periodo: {settings['shiller']['history_start']} → {settings['validation']['development_end'][:7]}.")
        print("Se leerán únicamente las fechas, precios medios y dividendos anualizados del periodo de desarrollo y su historia previa.")
        print("La evaluación desde 1990 seguirá excluida de la tabla preparada.")
    else:
        print("Trabajar con SPY — ETF, datos diarios de Yahoo Finance")
        print(f"Periodo: {settings['spy']['start']} → {settings['spy']['end']} (fin exclusivo).")
        print("Es el trabajo previo con SPY; no se unirá esta serie con Shiller.")
        print("Su utilización definitiva en el estudio sigue pendiente.")
    proceed, file = _select_input(settings, source)
    if not proceed:
        return False
    if source == "shiller":
        print("Se regenerará la tabla mensual. Las señales anteriores de este flujo se retirarán al terminar correctamente.")
        print("Preparando datos de Shiller…", flush=True)
        summary = prepare_shiller_data(config, file=file)
        show_result("shiller_monthly", summary)
    else:
        print("Preparando datos diarios de SPY…", flush=True)
        summary = prepare_spy_data(config, file=file)
        show_result("spy_prices", summary)
    print("Consulta los archivos desde la opción 3; los originales anteriores permanecen intactos.")
    return True


def _show_configuration(config: Path, settings: dict) -> None:
    print("Configuración del estudio")
    print(f"Archivo: {config}")
    print(f"Shiller: observaciones mensuales; historia previa desde {settings['shiller']['history_start']}.")
    print(f"Desarrollo: {settings['validation']['development_start']} → {settings['validation']['development_end']}.")
    print(f"Evaluación: desde {settings['validation']['final_test_start']}; fecha final pendiente y evaluación deshabilitada.")
    print("Momentum: P[m−1]/P[m−12]−1; positivo propone largo y no positivo propone efectivo.")
    print("Reversión: movimiento de un mes; propone operar en el sentido contrario.")
    print("Ambas señales se asignan al mes posterior a la decisión; todavía no son operaciones simuladas.")
    print(f"SPY: diario, {settings['spy']['start']} → {settings['spy']['end']} (fin exclusivo), separado de Shiller.")
    print("Las salidas se regeneran en data/processed con nombres fijos.")
    print(f"Carpeta del proyecto: {settings['root']}")
    print("Puedes editar estudio.toml y volver al menú; la configuración se vuelve a leer antes de cada tarea.")


def _next_step(settings: dict, name: str) -> str:
    if name == "shiller_signals":
        try:
            load_monthly(settings)
        except (OSError, ValueError, KeyError, TypeError):
            return "1. Preparar datos de Shiller; después 2. Calcular señales"
    return RESULTS[name][1]


def show_project_summary(settings: dict) -> None:
    print("Datos y señales del flujo actual")
    for name, (label, _) in RESULTS.items():
        try:
            _, summary = read_result(settings, name)
            print(f"  {label}: disponible para consultar ({summary['rows']} filas).")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"  {label}: pendiente. {exc}")
            print(f"    Para resolverlo: {_next_step(settings, name)}.")
    print("Se consultan los archivos de trabajo con nombres fijos; los resultados históricos se conservan en sus carpetas.")


def _consult(settings: dict) -> None:
    names = list(RESULTS)
    while True:
        _clear_screen()
        show_project_summary(settings)
        print("\n¿Qué quieres ver?")
        for number, name in enumerate(names, 1):
            print(f"{number}. {RESULTS[name][0]}")
        print("0. Volver al menú principal")
        answer = _choice("Opción: ", {"0", "1", "2", "3"})
        if answer == "0":
            return
        name = names[int(answer) - 1]
        _clear_screen()
        try:
            table, summary = read_result(settings, name)
            show_result(name, summary)
            columns = ({"period": "Mes", "price_monthly_mean": "Precio medio", "dividend_annualized": "Dividendo anualizado"}
                       if name == "shiller_monthly" else
                       {"decision_period": "Decisión", "target_period": "Mes objetivo", "momentum_signal": "Momentum", "reversal_signal": "Reversión"}
                       if name == "shiller_signals" else {"observed_at": "Fecha", "adjusted_close": "Cierre ajustado"})
            print("\nPrimeras cinco filas (consulta sin modificar archivos):")
            sample = table[list(columns)].head(5).rename(columns=columns).astype("string").fillna("Sin historia")
            print(sample.to_string(index=False))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"No se puede consultar: {exc}")
            print(f"Siguiente paso: {_next_step(settings, name)}.")
        if not _pause():
            raise EOFError


def interactive_menu(config_path: str | Path = DEFAULT_CONFIG) -> int:
    """Elegir una tarea; 0 vuelve, Ctrl+C cancela y EOF cierra el menú."""
    config_path = Path(config_path).expanduser().resolve()
    while True:
        option = ""
        try:
            _clear_screen()
            try:
                settings = load_config(config_path)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print(f"No se puede leer la configuración: {exc}")
                print(f"Revisa {config_path} y guarda los cambios.")
                print("1. Reintentar después de corregir el archivo\n0. Salir")
                if _choice("Opción: ", {"0", "1"}) == "0":
                    return 0
                continue
            print("TFM — ¿Invertir o esperar?")
            print(f"Estudio actual: Shiller mensual; desarrollo {settings['validation']['development_start'][:4]}–{settings['validation']['development_end'][:4]}.")
            print("Disponible: preparación de datos y cálculo de señales.")
            print("Pendiente: definir la simulación con el tutor; todavía no hay modelos entrenados.")
            print("\n1. Preparar datos de Shiller\n2. Calcular señales de momentum y reversión\n3. Consultar datos y señales preparados\n4. Trabajar con datos de SPY de Yahoo Finance\n5. Ver la configuración del estudio\n0. Salir")
            option = _choice("Opción del menú (0–5): ", {"0", "1", "2", "3", "4", "5"})
            if option == "0":
                return 0
            _clear_screen()
            if option in {"1", "4"}:
                if not _prepare(config_path, settings, "shiller" if option == "1" else "spy"):
                    continue
            elif option == "2":
                print("Calcular señales de Shiller — momentum 12–1 y reversión de un mes")
                print("Entrada: data/processed/shiller_monthly.parquet. No se descargarán datos.")
                print("Se mantienen las reglas originales. Este paso todavía no calcula ganancias ni entrena un modelo.")
                show_result("shiller_signals", calculate_signals(config_path))
            elif option == "3":
                _consult(settings)
                continue
            else:
                _show_configuration(config_path, settings)
        except EOFError:
            print("\nMenú cerrado.")
            return 0
        except KeyboardInterrupt:
            print("\nOperación cancelada. Puedes volver a elegir una tarea.")
        except (DownloadError, OSError, ValueError, KeyError, TypeError) as exc:
            print(f"No se ha completado la tarea: {exc}")
            if option == "2":
                print("Si faltan datos de Shiller, usa la opción 1 antes de calcular señales.")
                print("Después repite la opción 2. No se han calculado rentabilidades.")
            else:
                print("Revisa el archivo indicado o la conexión si estabas descargando; después repite la opción elegida.")
        if not _pause():
            return 0


# Presentación de comandos anteriores; se retirará con ellos en el tercer incremento.
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
