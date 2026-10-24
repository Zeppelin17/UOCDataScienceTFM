"""Recorridos guiados del TFM: fuente, tarea, resultado y siguiente paso."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys

from tfm.config import DEFAULT_CONFIG, load_config
from tfm.data import prepare_shiller_data, prepare_spy_data, calculate_signals, load_monthly, read_result, prepare_french_data, prepare_return_components
from tfm.sources.prices import DownloadError


RESULTS = {
    "shiller_monthly": ("Datos mensuales de Shiller", "1. Preparar datos de Shiller"),
    "shiller_signals": ("Señales de momentum y reversión", "2. Calcular señales"),
    "spy_prices": ("Datos diarios del ETF SPY", "4. Trabajar con datos de SPY"),
    "french_rf_monthly": ("Rentabilidad del efectivo (RF de French)", "6. Preparar RF de French"),
    "monthly_return_components": ("Componentes de rentabilidad mensual", "7. Preparar componentes de rentabilidad"),
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
    filename = {"shiller": "shiller.xls", "spy": "spy.parquet", "french": "french_factors.zip"}[source]
    raw = settings["root"] / "data/raw" / filename
    if raw.exists():
        print(f"Origen: original de trabajo guardado en data/raw/{raw.name}.")
        print("Se reutilizará sin descargar ni sustituir el original.")
        return True, None
    print("Todavía no hay un original de trabajo para esta fuente.")
    items = [] if source == "french" else _history(settings, source)
    print("1. Descargar de la fuente configurada")
    print("2. Importar un archivo de mi ordenador")
    if items:
        print(f"3. Reutilizar un original de la etapa anterior ({len(items)} disponibles)")
    print("0. Volver sin preparar datos")
    answer = _choice("¿De dónde obtenemos los datos? ", {"0", "1", "2"} | ({"3"} if items else set()))
    if answer == "0":
        return False, None
    if answer == "1":
        print({"shiller": "Origen: descarga del Excel oficial de Shiller.",
               "spy": "Origen: Yahoo Finance mediante yfinance.",
               "french": "Origen: ZIP mensual oficial de Kenneth French."}[source])
        return True, None
    if answer == "3":
        selected = _select_history(items, source)
        return selected is not None, selected
    print({"shiller": "Pega la ruta del XLS original de Shiller.",
           "french": "Pega la ruta del ZIP mensual original de tres factores de French.",
           "spy": "Pega la ruta del Parquet original de Yahoo. Conserva junto a él su JSON de procedencia (spy_fuente.json o manifest.json), con el periodo solicitado."}[source])
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
        print("Siguiente paso: opción 2 para calcular señales. La simulación aún requiere fijar sus supuestos.")
    elif name == "shiller_signals":
        print(f"Meses objetivo: {summary['target_start']} → {summary['target_end']} | {summary['rows']} meses")
        print(f"Meses con ambas señales disponibles: {summary['both_rules_available']}")
        print("+1: posición que se beneficiaría de una subida; -1: de una bajada; 0: efectivo.")
        print("Una señal vacía significa historia insuficiente, no una decisión de permanecer fuera.")
        for rule, label in (("momentum", "Momentum"), ("reversal", "Reversión")):
            if summary[f"missing_{rule}_targets"]:
                print(f"{label}, sin historia suficiente: {', '.join(summary[f'missing_{rule}_targets'])}")
        print("Señales sobre promedios mensuales, sin simulación de rentabilidades ni entrenamiento de modelos.")
        print("Siguiente paso: consulta las señales en la opción 3. La simulación aún requiere fijar sus supuestos.")
    elif name in {"french_rf_monthly", "monthly_return_components"}:
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['rows']} meses")
        if name == "french_rf_monthly":
            print("Solo RF de French, convertido de porcentaje mensual a decimal. No es la rentabilidad del S&P.")
            print("Siguiente paso: opción 7, una vez preparados los datos de Shiller.")
        else:
            print("Precio, dividendo aproximado y RF separados; rentabilidades en decimal mensual.")
            print("D/12 es una aproximación contable, no un pago observado. Los precios son promedios mensuales.")
            print("Todavía no se han aplicado señales, posiciones ni costes; no son resultados de estrategias.")
            print("Siguiente paso: revisar el notebook 02_componentes_de_rentabilidad.ipynb.")
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
    elif source == "french":
        print("Preparar RF de French — rentabilidad mensual del efectivo")
        print(f"Periodo: {settings['validation']['development_start'][:7]} → {settings['validation']['development_end'][:7]}.")
        print("Se extraerá solo RF. Los demás factores y los importes desde 1990 no se utilizarán.")
    else:
        print("Trabajar con SPY — ETF, datos diarios de Yahoo Finance")
        print(f"Periodo: {settings['spy']['start']} → {settings['spy']['end']} (fin exclusivo).")
        print("Es el trabajo previo con SPY; no se unirá esta serie con Shiller.")
        print("Su utilización definitiva en el estudio sigue pendiente.")
    proceed, file = _select_input(settings, source)
    if not proceed:
        return False
    if source == "shiller":
        print("Se regenerará la tabla mensual. Se retirarán las señales y los componentes anteriores al terminar correctamente.")
        print("Preparando datos de Shiller…", flush=True)
        summary = prepare_shiller_data(config, file=file)
        show_result("shiller_monthly", summary)
    elif source == "french":
        print("Se regenerará RF y se retirarán los componentes anteriores al terminar correctamente.")
        print("Preparando RF mensual…", flush=True)
        show_result("french_rf_monthly", prepare_french_data(config, file=file))
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
    print("French: solo RF mensual para el efectivo; sus porcentajes se convierten a decimal.")
    print("Componentes: P[t]/P[t−1]−1, D[t]/12/P[t−1] y RF[t]; aún sin posiciones ni costes.")
    print("Las salidas se regeneran en data/processed con nombres fijos.")
    print(f"Carpeta del proyecto: {settings['root']}")
    print("Puedes editar estudio.toml y volver al menú; la configuración se vuelve a leer antes de cada tarea.")


def _next_step(settings: dict, name: str) -> str:
    if name == "shiller_signals":
        try:
            load_monthly(settings)
        except (OSError, ValueError, KeyError, TypeError):
            return "1. Preparar datos de Shiller; después 2. Calcular señales"
    if name == "monthly_return_components":
        return "1. Preparar Shiller y 6. Preparar RF; después 7. Preparar componentes"
    return RESULTS[name][1]


def show_project_summary(settings: dict) -> None:
    print("Datos, señales y componentes del flujo actual")
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
        answer = _choice("Opción: ", {"0", *(str(i) for i in range(1, len(names) + 1))})
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
                       if name == "shiller_signals" else
                       {"period": "Mes", "rf_return": "RF (decimal mensual)"} if name == "french_rf_monthly" else
                       {"period": "Mes", "price_return": "Precio (decimal)", "dividend_return_approx": "Dividendo aprox. (decimal)",
                        "rf_return": "RF (decimal)"} if name == "monthly_return_components" else
                       {"observed_at": "Fecha", "adjusted_close": "Cierre ajustado"})
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
            print("Disponible: datos, señales y componentes de rentabilidad mensual.")
            print("Pendiente: fijar los supuestos de la simulación; todavía no hay modelos entrenados.")
            print("\n1. Preparar datos de Shiller\n2. Calcular señales de momentum y reversión\n3. Consultar datos y señales preparados\n4. Trabajar con datos de SPY de Yahoo Finance\n5. Ver la configuración del estudio\n6. Preparar RF de French (rentabilidad del efectivo)\n7. Preparar componentes de rentabilidad mensual\n0. Salir")
            option = _choice("Opción del menú (0–7): ", {"0", "1", "2", "3", "4", "5", "6", "7"})
            if option == "0":
                return 0
            _clear_screen()
            if option in {"1", "4", "6"}:
                source = {"1": "shiller", "4": "spy", "6": "french"}[option]
                if not _prepare(config_path, settings, source):
                    continue
            elif option == "2":
                print("Calcular señales de Shiller — momentum 12–1 y reversión de un mes")
                print("Entrada: data/processed/shiller_monthly.parquet. No se descargarán datos.")
                print("Se mantienen las reglas originales. Este paso todavía no calcula ganancias ni entrena un modelo.")
                show_result("shiller_signals", calculate_signals(config_path))
            elif option == "7":
                print("Preparar componentes — precio, dividendo aproximado y RF")
                print("Entrada: Shiller y RF ya preparados. No se descargan datos ni se aplican posiciones o costes.")
                show_result("monthly_return_components", prepare_return_components(config_path))
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
