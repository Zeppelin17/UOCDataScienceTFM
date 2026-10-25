"""Flujo local sencillo: originales, tablas preparadas y señales con rutas fijas."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

from tfm.config import DEFAULT_CONFIG, load_config
from tfm.preparation.prices import normalize_prices
from tfm.preparation.shiller import COLUMNS, normalize_shiller
from tfm.signals.shiller import WARNINGS, build_price_signals
from tfm.sources.prices import fetch_prices
from tfm.sources.shiller import INSTRUMENT, fetch_shiller
from tfm.sources.french import fetch_french
from tfm.preparation.french import normalize_french_rf, validate_rf
from tfm.returns import COLUMNS as RETURN_COLUMNS, FORMULAS, WARNINGS as RETURN_WARNINGS, build_return_components
from tfm.simulation import STRATEGIES, WARNINGS as SIMULATION_WARNINGS, simulate_baselines, summarize_baselines
from tfm.sensitivity import sensitivity_scenarios, run_sensitivities
from tfm.comparators import BEAR_STRATEGIES, BEAR_PROTOCOL, BEAR_WARNINGS, simulate_bear_comparison


def _simulation_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "baseline_simulations.parquet", processed / "baseline_simulations.json"


def _sensitivity_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "baseline_sensitivity.parquet", processed / "baseline_sensitivity.json"


def _bear_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "bear_filter_simulations.parquet", processed / "bear_filter_simulations.json"


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _publish(table: pd.DataFrame, path: Path, summary: dict, *, dependents: tuple[Path, ...] = ()) -> dict:
    """Guardar tabla y resumen; restaurar las salidas anteriores ante un error.

    La copia anterior vive solo en memoria durante esta operación local.
    Los dependientes se retiran después de sustituir la tabla y su resumen.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    report_path = path.with_suffix(".json")
    temporary = path.with_suffix(".parquet.tmp")
    temporary_report = path.with_suffix(".json.tmp")
    previous = {}
    changed = []
    try:
        table.to_parquet(temporary, index=False)
        _json(temporary_report, summary)
        previous = {p: p.read_bytes() if p.exists() else None for p in (path, report_path, *dependents)}
        temporary.replace(path)
        changed.append(path)
        temporary_report.replace(report_path)
        changed.append(report_path)
        for dependent in dependents:
            dependent.unlink(missing_ok=True)
            changed.append(dependent)
    except (Exception, KeyboardInterrupt):
        for target in reversed(changed):
            if previous[target] is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous[target])
        raise
    finally:
        temporary.unlink(missing_ok=True)
        temporary_report.unlink(missing_ok=True)
    return {**summary, "path": str(path)}


def _original(raw: Path, file: str | Path | None) -> Path | None:
    if raw.exists():
        if file is not None and Path(file).expanduser().resolve() != raw:
            raise ValueError(f"Ya existe el original {raw}. Ejecuta sin --file para reutilizarlo; no se ha sustituido.")
        return raw
    return Path(file).expanduser().resolve() if file is not None else None


def _save_original(raw: Path, content: bytes | pd.DataFrame, provenance: dict) -> None:
    if raw.exists():
        return
    raw.parent.mkdir(parents=True, exist_ok=True)
    info = raw.with_name(f"{raw.stem}_fuente.json")
    # El modo exclusivo también protege el original si otra ejecución lo creó.
    handle = raw.open("xb")
    try:
        with handle:
            if isinstance(content, bytes):
                handle.write(content)
            else:
                content.to_parquet(handle, index=True)
            _json(info, {**provenance, "saved_at_utc": datetime.now(timezone.utc).isoformat()})
    except (Exception, KeyboardInterrupt):
        raw.unlink(missing_ok=True)
        info.unlink(missing_ok=True)
        raise


def _window(settings: dict) -> dict:
    return {"history_start": settings["shiller"]["history_start"], **settings["validation"]}


def _check_spy_original(path: Path, period: dict) -> None:
    """Comprobar el periodo declarado del original, sin certificar su calendario."""
    info_path = path.with_name(f"{path.stem}_fuente.json")
    if not info_path.exists():
        info_path = path.parent / "manifest.json"  # Originales de la etapa anterior.
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("No se puede leer la procedencia del original SPY. Conserva junto al Parquet su JSON de procedencia o utiliza una nueva descarga.") from exc
    if not isinstance(info, dict) or not isinstance(info.get("parameters"), dict):
        raise ValueError("El JSON de procedencia del original SPY no contiene los parámetros de descarga")
    parameters = info["parameters"]
    if (info.get("source", info.get("provider")) != "yahoo" or info.get("instrument") != "SPY"
            or parameters.get("tickers") != "SPY"):
        raise ValueError("La procedencia no corresponde a datos de SPY de Yahoo Finance")
    if any(parameters.get(key) != period[key] for key in ("start", "end")):
        raise ValueError(
            f"El periodo del original SPY ({parameters.get('start')} → {parameters.get('end')}, fin exclusivo) "
            f"no coincide con el solicitado ({period['start']} → {period['end']}). "
            "Utiliza un original de ese periodo o conserva una copia del original de trabajo "
            "y retíralo de data/raw/spy.parquet antes de descargar otro. No se han modificado los datos."
        )


def prepare_shiller_data(config: str | Path = DEFAULT_CONFIG, *, file: str | Path | None = None) -> dict:
    settings = load_config(config)
    root = settings["root"]
    raw = root / "data/raw/shiller.xls"
    selected = _original(raw, file)
    content, acquisition = fetch_shiller(url=settings["shiller"]["url"], file=selected)
    table, report = normalize_shiller(content, history_start=settings["shiller"]["history_start"],
                                      policy_bytes=settings["policy_bytes"])
    if report["status"] != "passed":
        errors = ", ".join(f"{key}: {value}" for key, value in report["error_counts"].items() if value)
        raise ValueError(f"No se han preparado los datos de Shiller ({errors}). Revisa el original; no se han rellenado valores.")
    _save_original(raw, content, {"source": "shiller", "url": settings["shiller"]["url"],
                                  "acquisition": acquisition})
    processed = root / "data/processed"
    return _publish(table, processed / "shiller_monthly.parquet",
                    {**report, "configuration": _window(settings)},
                    dependents=(processed / "shiller_signals.parquet", processed / "shiller_signals.json",
                                processed / "monthly_return_components.parquet", processed / "monthly_return_components.json",
                                *_simulation_paths(processed), *_sensitivity_paths(processed), *_bear_paths(processed)))


def load_monthly(settings: dict) -> pd.DataFrame:
    path = settings["root"] / "data/processed/shiller_monthly.parquet"
    try:
        report = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        table = pd.read_parquet(path)
    except FileNotFoundError as exc:
        raise ValueError("Faltan datos de Shiller preparados. Ejecuta primero prepare-data.") from exc
    if not isinstance(report, dict):
        raise ValueError("El resumen de Shiller no es válido. Vuelve a preparar los datos.")
    if report.get("configuration") != _window(settings):
        raise ValueError("Los periodos han cambiado. Vuelve a preparar los datos antes de calcular señales.")
    months = pd.period_range(settings["shiller"]["history_start"], settings["validation"]["development_end"][:7], freq="M").astype(str).tolist()
    start = settings["validation"]["development_start"][:7]
    if (report.get("status") != "passed" or table.columns.tolist() != COLUMNS
            or table.period.tolist() != months or report.get("rows") != len(table)
            or not table.asset.eq(INSTRUMENT).all() or not table.source.eq("shiller").all()
            or table.sample_role.tolist() != ["history" if month < start else "development" for month in months]):
        raise ValueError("La tabla de Shiller no tiene los meses o columnas esperados. Vuelve a preparar los datos.")
    for name in ("price_monthly_mean", "dividend_annualized"):
        values = table[name]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or not values.map(math.isfinite).all()
                or (values.le(0).any() if name == "price_monthly_mean" else values.lt(0).any())):
            raise ValueError("La tabla contiene importes inválidos. Vuelve a preparar los datos de Shiller.")
    return table


def calculate_signals(config: str | Path = DEFAULT_CONFIG) -> dict:
    settings = load_config(config)
    signals = build_price_signals(load_monthly(settings))
    start, end = (settings["validation"][key][:7] for key in ("development_start", "development_end"))
    signals = signals.loc[signals.target_period.between(start, end)].reset_index(drop=True)
    if signals.target_period.tolist() != pd.period_range(start, end, freq="M").astype(str).tolist():
        raise ValueError("No se cubren todos los meses objetivo del desarrollo")
    common = signals.loc[signals.both_rules_available, "target_period"]
    if common.empty:
        raise ValueError("No hay meses con historia suficiente para las dos reglas")
    summary = {"rows": len(signals), "target_start": start, "target_end": end,
               "both_rules_available": len(common), "first_common_target": common.iloc[0],
               "missing_momentum_targets": signals.loc[signals.momentum_signal.isna(), "target_period"].tolist(),
               "missing_reversal_targets": signals.loc[signals.reversal_signal.isna(), "target_period"].tolist(),
               "configuration": {**_window(settings), "signals": settings["signals"]},
               "warnings": WARNINGS}
    return _publish(signals, settings["root"] / "data/processed/shiller_signals.parquet", summary,
                    dependents=(*_simulation_paths(settings["root"] / "data/processed"),
                                *_sensitivity_paths(settings["root"] / "data/processed"),
                                *_bear_paths(settings["root"] / "data/processed")))


def _rf_configuration(settings: dict) -> dict:
    return {"url": settings["french"]["url"],
            "development_start": settings["validation"]["development_start"],
            "development_end": settings["validation"]["development_end"]}


def _return_configuration(settings: dict) -> dict:
    return {**_window(settings), "french": _rf_configuration(settings)}


def prepare_french_data(config: str | Path = DEFAULT_CONFIG, *, file: str | Path | None = None) -> dict:
    settings = load_config(config)
    root = settings["root"]
    raw = root / "data/raw/french_factors.zip"
    content, acquisition = fetch_french(url=settings["french"]["url"], file=_original(raw, file))
    start, end = (settings["validation"][key][:7] for key in ("development_start", "development_end"))
    table, report = normalize_french_rf(content, start=start, end=end)
    _save_original(raw, content, {"source": "kenneth_french", "url": settings["french"]["url"],
                                  "acquisition": acquisition})
    processed = root / "data/processed"
    return _publish(table, processed / "french_rf_monthly.parquet",
                    {**report, "configuration": _rf_configuration(settings)},
                    dependents=(processed / "monthly_return_components.parquet",
                                processed / "monthly_return_components.json", *_simulation_paths(processed), *_sensitivity_paths(processed), *_bear_paths(processed)))


def load_french_rf(settings: dict) -> tuple[pd.DataFrame, dict]:
    path = settings["root"] / "data/processed/french_rf_monthly.parquet"
    try:
        report = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        table = pd.read_parquet(path)
    except FileNotFoundError as exc:
        raise ValueError("Falta RF preparado. Usa la opción 6 o prepare-data --source french.") from exc
    if (not isinstance(report, dict) or report.get("status") != "passed"
            or report.get("configuration") != _rf_configuration(settings)
            or report.get("rows") != len(table) or report.get("output_unit") != "decimal_monthly_return"):
        raise ValueError("RF o su configuración no coinciden; vuelve a preparar French.")
    start, end = (settings["validation"][key][:7] for key in ("development_start", "development_end"))
    validate_rf(table, start=start, end=end)
    return table, {**report, "path": str(path)}


def prepare_return_components(config: str | Path = DEFAULT_CONFIG) -> dict:
    settings = load_config(config)
    monthly = load_monthly(settings)
    rf, _ = load_french_rf(settings)
    start, end = (settings["validation"][key][:7] for key in ("development_start", "development_end"))
    table = build_return_components(monthly, rf, start=start, end=end)
    report = {"status": "passed", "rows": len(table), "first_period": start, "last_period": end,
              "unit": "decimal_monthly_return", "basis": "monthly_mean_price",
              "formulas": FORMULAS, "configuration": _return_configuration(settings),
              "warnings": RETURN_WARNINGS}
    return _publish(table, settings["root"] / "data/processed/monthly_return_components.parquet", report,
                    dependents=(*_simulation_paths(settings["root"] / "data/processed"),
                                *_sensitivity_paths(settings["root"] / "data/processed"),
                                *_bear_paths(settings["root"] / "data/processed")))


def _simulation_configuration(settings: dict) -> dict:
    return {"data": _return_configuration(settings), "signals": settings["signals"],
            "simulation": settings["simulation"]}


def simulate_basic_strategies(config: str | Path = DEFAULT_CONFIG) -> dict:
    settings = load_config(config)
    components, _ = read_result(settings, "monthly_return_components")
    signals, _ = read_result(settings, "shiller_signals")
    table = simulate_baselines(components, signals, settings["simulation"])
    report = {"status": "passed", "rows": len(table), "months_per_strategy": len(components),
              "first_period": components.period.iloc[0], "last_period": components.period.iloc[-1],
              "configuration": _simulation_configuration(settings), "liquidated_at_end": True,
              "strategies": summarize_baselines(table, settings["simulation"]),
              "warnings": SIMULATION_WARNINGS}
    return _publish(table, settings["root"] / "data/processed/baseline_simulations.parquet", report)


def analyze_sensitivity(config: str | Path = DEFAULT_CONFIG) -> dict:
    settings = load_config(config)
    components, _ = read_result(settings, "monthly_return_components")
    signals, _ = read_result(settings, "shiller_signals")
    table = run_sensitivities(components, signals, settings["simulation"])
    report = {"status": "passed", "rows": len(table), "months_per_strategy": len(components),
              "first_period": components.period.iloc[0], "last_period": components.period.iloc[-1],
              "configuration": _simulation_configuration(settings),
              "scenarios": sensitivity_scenarios(settings["simulation"]),
              "comparisons": table.astype(object).where(pd.notna(table), None).to_dict("records"),
              "warnings": [*SIMULATION_WARNINGS,
                           "Un supuesto cada vez; no es una búsqueda de parámetros ni certifica robustez fuera de muestra."]}
    return _publish(table, settings["root"] / "data/processed/baseline_sensitivity.parquet", report)


def simulate_bear_filter(config: str | Path = DEFAULT_CONFIG) -> dict:
    settings = load_config(config)
    components, _ = read_result(settings, "monthly_return_components")
    signals, _ = read_result(settings, "shiller_signals")
    table = simulate_bear_comparison(components, signals, load_monthly(settings), settings["simulation"])
    context = table.loc[table.strategy.eq("buy_and_hold")]
    report = {"status": "passed", "rows": len(table), "months_per_strategy": len(components),
              "first_period": components.period.iloc[0], "last_period": components.period.iloc[-1],
              "configuration": {**_simulation_configuration(settings), "bear_filter": BEAR_PROTOCOL},
              "bear_months": int(context.bear_market.sum()),
              "blocked_momentum_signals": int((context.bear_market & context.original_momentum_signal.ne(0)).sum()),
              "blocked_reversal_signals": int((context.bear_market & context.original_reversal_signal.ne(0)).sum()),
              "strategies": summarize_baselines(table, settings["simulation"], strategies=BEAR_STRATEGIES),
              "warnings": [*SIMULATION_WARNINGS, *BEAR_WARNINGS]}
    return _publish(table, settings["root"] / "data/processed/bear_filter_simulations.parquet", report)


def read_result(settings: dict, name: str) -> tuple[pd.DataFrame, dict]:
    """Consultar una salida del flujo nuevo y rechazar configuraciones antiguas."""
    if name == "bear_filter_simulations":
        read_result(settings, "monthly_return_components")
        read_result(settings, "shiller_signals")
        path = settings["root"] / "data/processed/bear_filter_simulations.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la comparación con filtro bajista. Usa la opción 10 o simulate-bear-filter.") from exc
        months = pd.period_range(settings["validation"]["development_start"][:7],
                                settings["validation"]["development_end"][:7], freq="M").astype(str).tolist()
        required = {"strategy", "period", "decision_period", "position", "capital_start", "capital_end", "net_return",
                    "price_pnl", "dividend_pnl", "cash_interest", "transaction_cost", "borrow_cost", "liquidation_cost",
                    "lookback_start_period", "lookback_start_price", "decision_price", "market_return_24m", "bear_market",
                    "original_momentum_signal", "original_reversal_signal"}
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("configuration") != {**_simulation_configuration(settings), "bear_filter": BEAR_PROTOCOL}
                or summary.get("rows") != len(table) or not required <= set(table)
                or len(table) != len(months) * len(BEAR_STRATEGIES) or set(table.strategy) != set(BEAR_STRATEGIES)
                or any(table.loc[table.strategy.eq(name), "period"].tolist() != months for name in BEAR_STRATEGIES)):
            raise ValueError("La comparación bajista o su configuración no coinciden; repite la opción 10.")
        numeric = table.drop(columns=["strategy", "period", "decision_period", "lookback_start_period", "bear_market"])
        if (any(not pd.api.types.is_numeric_dtype(numeric[c]) or numeric[c].isna().any()
                or not numeric[c].map(math.isfinite).all() for c in numeric)
                or not pd.api.types.is_bool_dtype(table.bear_market) or table.bear_market.isna().any()
                or table.capital_end.le(0).any()):
            raise ValueError("La comparación bajista contiene importes inválidos; repite la opción 10.")
        return table, {**summary, "path": str(path)}
    if name == "baseline_sensitivity":
        read_result(settings, "monthly_return_components")
        read_result(settings, "shiller_signals")
        path = settings["root"] / "data/processed/baseline_sensitivity.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la comparación de supuestos. Usa la opción 9 o analyze-sensitivity.") from exc
        scenarios = sensitivity_scenarios(settings["simulation"])
        expected = [(scenario["scenario"], strategy) for scenario in scenarios for strategy in STRATEGIES]
        required = {"scenario", "scenario_label", "changed_assumption", "strategy", "months", "label",
                    *settings["simulation"], "capital_final", "total_return", "annualized_return",
                    "annualized_volatility", "sharpe", "max_drawdown", "annualized_turnover",
                    "transaction_cost_total", "borrow_cost_total", "annualized_return_delta"}
        months = len(pd.period_range(settings["validation"]["development_start"][:7],
                                     settings["validation"]["development_end"][:7], freq="M"))
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("configuration") != _simulation_configuration(settings)
                or summary.get("scenarios") != scenarios or summary.get("rows") != len(table)
                or not required <= set(table)
                or list(zip(table.scenario, table.strategy)) != expected
                or not table.months.eq(months).all()):
            raise ValueError("La comparación o su configuración no coinciden; repite la opción 9.")
        for scenario in scenarios:
            rows = table.loc[table.scenario.eq(scenario["scenario"])]
            if any(not rows[key].eq(value).all() for key, value in scenario["parameters"].items()):
                raise ValueError("Los supuestos de la comparación no coinciden; repite la opción 9.")
        numeric = table.drop(columns=["scenario", "scenario_label", "changed_assumption", "strategy", "label", "include_dividends"])
        for column in numeric:
            values = numeric[column].dropna() if column == "sharpe" else numeric[column]
            if (not pd.api.types.is_numeric_dtype(values) or values.isna().any()
                    or not values.map(math.isfinite).all()):
                raise ValueError("La comparación contiene métricas inválidas; repite la opción 9.")
        if table.capital_final.le(0).any():
            raise ValueError("La comparación contiene capital no positivo; repite la opción 9.")
        return table, {**summary, "path": str(path)}
    if name == "baseline_simulations":
        read_result(settings, "monthly_return_components")
        read_result(settings, "shiller_signals")
        path = settings["root"] / "data/processed/baseline_simulations.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la simulación básica. Usa la opción 8 o simulate-baselines.") from exc
        months = pd.period_range(settings["validation"]["development_start"][:7],
                                settings["validation"]["development_end"][:7], freq="M").astype(str).tolist()
        required = {"strategy", "period", "decision_period", "position", "capital_start", "capital_end", "net_return",
                    "price_pnl", "dividend_pnl", "cash_interest", "transaction_cost", "borrow_cost", "liquidation_cost"}
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("configuration") != _simulation_configuration(settings)
                or summary.get("rows") != len(table) or not required <= set(table)
                or len(table) != len(months) * len(STRATEGIES)
                or set(table.strategy) != set(STRATEGIES)
                or any(table.loc[table.strategy.eq(name), "period"].tolist() != months for name in STRATEGIES)):
            raise ValueError("La simulación o su configuración no coinciden; vuelve a simular.")
        numeric = table.drop(columns=["strategy", "period", "decision_period"])
        if (any(not pd.api.types.is_numeric_dtype(numeric[c]) or not numeric[c].map(math.isfinite).all() for c in numeric)
                or table.capital_end.le(0).any()):
            raise ValueError("La simulación contiene importes inválidos; vuelve a simular.")
        return table, {**summary, "path": str(path)}
    if name == "french_rf_monthly":
        return load_french_rf(settings)
    if name == "monthly_return_components":
        load_monthly(settings)
        load_french_rf(settings)
        path = settings["root"] / "data/processed/monthly_return_components.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Faltan componentes de rentabilidad. Usa la opción 7 o prepare-returns.") from exc
        months = pd.period_range(settings["validation"]["development_start"][:7],
                                settings["validation"]["development_end"][:7], freq="M").astype(str).tolist()
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("configuration") != _return_configuration(settings)
                or summary.get("rows") != len(table) or table.columns.tolist() != RETURN_COLUMNS
                or table.period.tolist() != months or summary.get("unit") != "decimal_monthly_return"):
            raise ValueError("Los componentes o su configuración no coinciden; vuelve a prepararlos.")
        numeric = table.drop(columns=["asset", "period", "previous_period"])
        if any(not pd.api.types.is_numeric_dtype(numeric[c]) or pd.api.types.is_bool_dtype(numeric[c])
               or not numeric[c].map(math.isfinite).all() for c in numeric):
            raise ValueError("Los componentes contienen importes inválidos; vuelve a prepararlos.")
        return table, {**summary, "path": str(path)}
    if name not in {"shiller_monthly", "shiller_signals", "spy_prices"}:
        raise ValueError("Resultado desconocido")
    path = settings["root"] / "data/processed" / f"{name}.parquet"
    try:
        if name == "shiller_monthly":
            table = load_monthly(settings)
        else:
            if name == "shiller_signals":
                load_monthly(settings)  # Las señales dependen de la preparación actual.
            table = pd.read_parquet(path)
        summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        message = ("Faltan los datos de SPY o su resumen. Vuelve a preparar los datos de SPY."
                   if name == "spy_prices" else
                   "Faltan las señales de Shiller o su resumen. Vuelve a calcular las señales.")
        raise ValueError(message) from exc
    if not isinstance(summary, dict):
        raise ValueError("El resumen no es válido; regenera el resultado.")
    expected = (settings["spy"] if name == "spy_prices" else _window(settings))
    if name == "shiller_signals":
        expected = {**expected, "signals": settings["signals"]}
    if summary.get("configuration") != expected:
        raise ValueError("La configuración ha cambiado; regenera este resultado antes de consultarlo.")
    required = ({"observed_at", "adjusted_close"} if name == "spy_prices" else
                {"decision_period", "target_period", "momentum_signal", "reversal_signal", "both_rules_available"}
                if name == "shiller_signals" else set(COLUMNS))
    if table.empty or len(table) != summary.get("rows") or not required <= set(table.columns):
        raise ValueError("La tabla y el resumen no coinciden; regenera el resultado.")
    if name == "shiller_signals":
        months = pd.period_range(settings["validation"]["development_start"][:7],
                                settings["validation"]["development_end"][:7], freq="M").astype(str).tolist()
        if (table.target_period.tolist() != months
                or table.both_rules_available.sum() != summary.get("both_rules_available")):
            raise ValueError("Las señales no cubren los meses esperados; vuelve a calcularlas.")
    return table, {**summary, "path": str(path)}


def prepare_spy_data(config: str | Path = DEFAULT_CONFIG, *, file: str | Path | None = None) -> dict:
    settings = load_config(config)
    root = settings["root"]
    raw = root / "data/raw/spy.parquet"
    selected = _original(raw, file)
    if selected is not None:
        _check_spy_original(selected, settings["spy"])
    parameters = {"tickers": "SPY", "start": settings["spy"]["start"], "end": settings["spy"]["end"],
                  "interval": "1d", "auto_adjust": False,
                  "back_adjust": False, "actions": True, "repair": False, "keepna": True,
                  "rounding": False, "prepost": False, "threads": False, "multi_level_index": False,
                  "ignore_tz": True, "timeout": 30, "progress": False, "group_by": "column"}
    frame = pd.read_parquet(selected) if selected is not None else fetch_prices(parameters)
    table, report = normalize_prices(frame)
    if (not table.observed_at.ge(pd.Timestamp(parameters["start"])).all()
            or not table.observed_at.lt(pd.Timestamp(parameters["end"])).all()):
        raise ValueError("El original SPY contiene fechas fuera del intervalo configurado; no se ha recortado ni sustituido.")
    if report["status"] != "passed":
        errors = ", ".join(f"{key}: {value}" for key, value in report["error_counts"].items() if value)
        raise ValueError(f"No se han preparado los datos de SPY ({errors}). Revisa el original.")
    origin = {"source": "yahoo", "instrument": "SPY", "parameters": parameters,
              "method": "local_file_import" if selected is not None else "yfinance_download"}
    if selected is not None:
        origin["input_path"] = str(selected)
    _save_original(raw, frame, origin)
    return _publish(table, root / "data/processed/spy_prices.parquet",
                    {"rows": len(table), "first_session": report["first_session"],
                     "last_session": report["last_session"], "status": report["status"],
                     "configuration": settings["spy"],
                     "warnings": ["Datos diarios del ETF SPY, separados del estudio de Shiller.",
                                  "Solo se comprueba estructura: no se certifican calendario, ajustes ni exactitud financiera."]})
