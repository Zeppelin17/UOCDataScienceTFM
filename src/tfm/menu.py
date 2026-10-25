"""Recorridos guiados del TFM: fuente, tarea, resultado y siguiente paso."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys

import pandas as pd

from tfm.config import DEFAULT_CONFIG, load_config
from tfm.data import prepare_shiller_data, prepare_spy_data, calculate_signals, load_monthly, read_result, prepare_french_data, prepare_return_components, simulate_basic_strategies, analyze_sensitivity, simulate_bear_filter, compare_simple_strategies
from tfm.sources.prices import DownloadError


RESULTS = {
    "shiller_monthly": ("Datos mensuales de Shiller", "1. Preparar datos de Shiller"),
    "shiller_signals": ("Señales de momentum y reversión", "2. Calcular señales"),
    "spy_prices": ("Datos diarios del ETF SPY", "4. Trabajar con datos de SPY"),
    "french_rf_monthly": ("Rentabilidad del efectivo (RF de French)", "6. Preparar RF de French"),
    "monthly_return_components": ("Componentes de rentabilidad mensual", "7. Preparar componentes de rentabilidad"),
    "baseline_simulations": ("Simulación de estrategias básicas", "8. Simular estrategias básicas"),
    "baseline_sensitivity": ("Comparación de costes y dividendos", "9. Comparar costes y dividendos"),
    "bear_filter_simulations": ("Comparación con filtro de mercado bajista", "10. Comparar con filtro bajista"),
    "simple_comparisons": ("Comparación conjunta de alternativas sencillas", "11. Comparar reglas, filtro bajista y volatilidad"),
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
    if name == "simple_comparisons":
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['months_per_strategy']} meses por cuenta")
        params = summary["configuration"]["volatility_scaling"]
        print(f"Riesgo: {params['lookback_months']} variaciones mensuales previas; objetivo anual {100 * params['target_annual_volatility']:g} %; exposición máxima {100 * params['max_exposure']:g} %.")
        print("Se comparan ocho cuentas con los mismos costes. Filtro bajista y escalado son alternativas separadas.")
        rows = [{"Estrategia": row["label"], "Anualizada (%)": round(100 * row["annualized_return"], 3),
                 "Volatilidad (%)": round(100 * row["annualized_volatility"], 3),
                 "Caída máx. (%)": round(100 * row["max_drawdown"], 3),
                 "Sharpe": round(row["sharpe"], 3) if row["sharpe"] is not None else "Sin valor"}
                for row in summary["strategies"]]
        print(pd.DataFrame(rows).to_string(index=False))
        print("El escalado reduce tamaño sin cambiar dirección; el efectivo restante cobra RF y los reajustes tienen coste.")
        print("Comprar y mantener ajustado permite separar el efecto de gestionar riesgo del efecto de la señal.")
        print("Objetivo de riesgo orientativo, sin apalancamiento. Adaptaciones a Shiller, no réplicas de artículos.")
        print("Siguiente paso: notebook 06_ajuste_volatilidad.ipynb. Modelos y evaluación desde 1990 siguen pendientes.")
    elif name == "bear_filter_simulations":
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['months_per_strategy']} meses por cuenta")
        print("Filtro: si P[m]/P[m−24]−1 < 0, permanecer en efectivo en m+1; si no, seguir la señal original.")
        print(f"Meses bajistas: {summary['bear_months']} | Señales bloqueadas: momentum {summary['blocked_momentum_signals']}, reversión {summary['blocked_reversal_signals']}")
        rows = [{"Estrategia": row["label"], "Anualizada (%)": round(100 * row["annualized_return"], 3),
                 "Caída máx. (%)": round(100 * row["max_drawdown"], 3),
                 "Sharpe": round(row["sharpe"], 3) if row["sharpe"] is not None else "Sin valor"}
                for row in summary["strategies"]]
        print(pd.DataFrame(rows).to_string(index=False))
        print("Adaptación del indicador de Daniel y Moskowitz a precios medios de Shiller; no réplica del artículo.")
        print("Mismas fechas y costes. El filtro no usa el rebote futuro ni cambia el sentido de una señal.")
        print("Desarrollo hasta 1989. La opción 11 añade ajuste por volatilidad; los modelos siguen pendientes.")
        print("Siguiente paso: notebook 05_filtro_bajista.ipynb para entender qué señales se bloquean.")
    elif name == "baseline_sensitivity":
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['months_per_strategy']} meses por estrategia")
        print(f"{len(summary['scenarios'])} escenarios. Se cambia un supuesto cada vez respecto a estudio.toml.")
        print("El central se conserva; no se ordenan ni seleccionan escenarios por rentabilidad.")
        for strategy in ("buy_and_hold", "momentum", "reversal"):
            rows = [row for row in summary["comparisons"] if row["strategy"] == strategy]
            print(f"\n{rows[0]['label']}:")
            view = [{"Escenario": row["scenario_label"],
                     "Anualizada (%)": round(100 * row["annualized_return"], 3),
                     "Cambio (p.p.)": round(100 * row["annualized_return_delta"], 3),
                     "Caída máx. (%)": round(100 * row["max_drawdown"], 3)} for row in rows]
            print(pd.DataFrame(view).to_string(index=False))
        print("Cambio: diferencia de rentabilidad anualizada respecto al central, en puntos porcentuales.")
        print("El préstamo afecta solo a posiciones cortas. Omitir dividendos también elimina su pago en cortos.")
        print("Aproximación histórica de desarrollo, sin evaluación desde 1990 ni búsqueda del mejor coste.")
        print("Siguiente paso: notebook 04_sensibilidad.ipynb para comparar y entender los escenarios.")
    elif name == "baseline_simulations":
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['months_per_strategy']} meses por estrategia")
        params = summary["configuration"]["simulation"]
        print(f"Capital inicial: {params['initial_capital']:g} | Negociación: {100 * params['transaction_cost_rate']:g} % | Préstamo anual: {100 * params['annual_borrow_rate']:g} %")
        print(f"Dividendos aproximados incluidos: {'sí' if params['include_dividends'] else 'no'}. Posiciones liquidadas al final.")
        rows = [{"Estrategia": row["label"], "Capital final": round(row["capital_final"], 2),
                 "Acumulada (%)": round(100 * row["total_return"], 2),
                 "Caída máxima (%)": round(100 * row["max_drawdown"], 2)} for row in summary["strategies"]]
        print(pd.DataFrame(rows).to_string(index=False))
        print("Aproximación histórica con precios medios y costes hipotéticos; no operaciones ejecutables.")
        print("Son resultados de desarrollo, sin filtros ni evaluación desde 1990.")
        print("Siguiente paso: notebook 03 para entender la cuenta; opción 9 para comparar costes y dividendos.")
    elif name == "shiller_monthly":
        print(f"Periodo: {summary['first_period']} → {summary['last_period']} | {summary['rows']} meses")
        print(f"Historia previa: {summary['history_rows']} meses | Desarrollo: {summary['development_rows']} meses")
        print("Sin meses ausentes ni duplicados; valores numéricos dentro de las condiciones exigidas.")
        print("P es un precio medio mensual; D es anualizado e interpolado, no un pago mensual observado.")
        print("Siguiente paso: opción 2 para calcular señales; después prepara RF y componentes con 6 y 7.")
    elif name == "shiller_signals":
        print(f"Meses objetivo: {summary['target_start']} → {summary['target_end']} | {summary['rows']} meses")
        print(f"Meses con ambas señales disponibles: {summary['both_rules_available']}")
        print("+1: posición que se beneficiaría de una subida; -1: de una bajada; 0: efectivo.")
        print("Una señal vacía significa historia insuficiente, no una decisión de permanecer fuera.")
        for rule, label in (("momentum", "Momentum"), ("reversal", "Reversión")):
            if summary[f"missing_{rule}_targets"]:
                print(f"{label}, sin historia suficiente: {', '.join(summary[f'missing_{rule}_targets'])}")
        print("Señales sobre promedios mensuales, sin simulación de rentabilidades ni entrenamiento de modelos.")
        print("Siguiente paso: consulta las señales en la opción 3. Con RF y componentes preparados, usa 8 para simular.")
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
    params = settings["simulation"]
    print(f"Simulación: capital {params['initial_capital']:g}, negociación {100 * params['transaction_cost_rate']:g} %, préstamo anual {100 * params['annual_borrow_rate']:g} %.")
    risk = settings["volatility_scaling"]
    print(f"Ajuste por volatilidad: {risk['lookback_months']} meses, objetivo anual {100 * risk['target_annual_volatility']:g} %, exposición máxima {100 * risk['max_exposure']:g} %.")
    print("Las salidas se regeneran en data/processed con nombres fijos.")
    print(f"Carpeta del proyecto: {settings['root']}")
    print("Puedes editar estudio.toml y volver al menú; la configuración se vuelve a leer antes de cada tarea.")


def _next_step(settings: dict, name: str) -> str:
    if name == "shiller_signals":
        try:
            load_monthly(settings)
        except (OSError, ValueError, KeyError, TypeError):
            return "1. Preparar datos de Shiller; después 2. Calcular señales"
    if name == "simple_comparisons":
        return "1. Shiller desde 1924-12, 2. Señales, 6. RF, 7. Componentes; después 11. Comparar alternativas"
    if name == "bear_filter_simulations":
        return "1. Preparar Shiller desde 1924-12, 2. Señales, 6. RF, 7. Componentes; después 10. Comparar con filtro bajista"
    if name in {"baseline_simulations", "baseline_sensitivity"}:
        return "1. Preparar Shiller, 2. Calcular señales, 6. Preparar RF, 7. Preparar componentes; después " + ("9. Comparar supuestos" if name == "baseline_sensitivity" else "8. Simular")
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
                       {"strategy": "Estrategia", "period": "Mes", "position": "Exposición", "net_return": "Neta (decimal)"} if name == "simple_comparisons" else
                       {"strategy": "Estrategia", "period": "Mes", "bear_market": "Bajista", "position": "Posición", "net_return": "Neta (decimal)"} if name == "bear_filter_simulations" else
                       {"scenario_label": "Escenario", "label": "Estrategia", "annualized_return": "Anualizada (decimal)"} if name == "baseline_sensitivity" else
                       {"strategy": "Estrategia", "period": "Mes", "position": "Posición", "net_return": "Neta (decimal)", "capital_end": "Capital final"} if name == "baseline_simulations" else
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
            print("Disponible: datos, reglas básicas, sensibilidad, filtro bajista y ajuste por volatilidad.")
            print("Desarrollo hasta 1989; evaluación desde 1990 deshabilitada. Todavía no hay filtros entrenados.")
            print("\n1. Preparar datos de Shiller\n2. Calcular señales de momentum y reversión\n3. Consultar datos y señales preparados\n4. Trabajar con datos de SPY de Yahoo Finance\n5. Ver la configuración del estudio\n6. Preparar RF de French (rentabilidad del efectivo)\n7. Preparar componentes de rentabilidad mensual\n8. Simular estrategias básicas\n9. Comparar costes y dividendos\n10. Comparar con filtro bajista\n11. Comparar reglas, filtro bajista y volatilidad\n0. Salir")
            option = _choice("Opción del menú (0–11): ", {str(i) for i in range(12)})
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
            elif option == "8":
                print("Simular estrategias básicas — comprar y mantener, momentum y reversión")
                print("Entradas: señales y componentes preparados. No se descargarán datos.")
                params = settings["simulation"]
                print(f"Supuestos: negociación {100 * params['transaction_cost_rate']:g} %, préstamo anual {100 * params['annual_borrow_rate']:g} %, dividendos {'incluidos' if params['include_dividends'] else 'excluidos'}.")
                print("Se cobran los reajustes de exposición y el cierre final. Son escenarios hipotéticos.")
                show_result("baseline_simulations", simulate_basic_strategies(config_path))
            elif option == "9":
                print("Comparar costes y dividendos — un supuesto cada vez")
                print("Entradas: señales y componentes preparados. No se descargan datos ni se cambian las reglas.")
                print("Negociación: 0 %, 0,10 %, 0,25 % y 0,50 %; préstamo anual: 0,25 %, 1 % y 3 %.")
                print("También se compara incluir/excluir el dividendo aproximado. El central es estudio.toml.")
                print("Se guardará una tabla comparativa; la simulación de la opción 8 se conserva.", flush=True)
                show_result("baseline_sensitivity", analyze_sensitivity(config_path))
            elif option == "10":
                print("Comparar con filtro bajista — caída de precios en los 24 meses anteriores")
                print("Si el indicador es negativo, se ignora la señal y se permanece en efectivo el mes siguiente.")
                print("Se aplica por separado a momentum y reversión. No se entrenan modelos ni se descargan datos.")
                print("Requiere Shiller preparado desde 1924-12 para comparar todos los meses de 1927–1989.")
                print("Se guardará una tabla separada con las cinco cuentas y sus decisiones.", flush=True)
                show_result("bear_filter_simulations", simulate_bear_filter(config_path))
            elif option == "11":
                print("Comparación conjunta — reglas originales, veto bajista y ajuste por volatilidad")
                print("Se mantiene la dirección de cada regla y se reduce el tamaño según el riesgo del índice.")
                print("Los supuestos están en [volatility_scaling] de estudio.toml. No se descargan datos ni se entrenan modelos.")
                print("Se guardan ocho cuentas en una tabla separada; no se sustituyen las simulaciones anteriores.", flush=True)
                show_result("simple_comparisons", compare_simple_strategies(config_path))
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
            elif option in {"8", "9", "10", "11"}:
                print("Entradas necesarias: 1. Shiller, 2. Señales, 6. RF y 7. Componentes; después repite esta opción.")
                print("Si hay insolvencia, revisa el escenario indicado; no se han omitido resultados para completar la tabla.")
            else:
                print("Revisa el archivo indicado o la conexión si estabas descargando; después repite la opción elegida.")
        if not _pause():
            return 0
