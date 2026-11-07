"""Preparación y lectura de tablas locales para los notebooks del estudio."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

from tfm.preparation.shiller import COLUMNS, normalize_shiller, preparation_window
from tfm.preparation.french import normalize_french_rf, validate_rf
from tfm.signals.shiller import WARNINGS, build_price_signals
from tfm.sources.shiller import INSTRUMENT, SOURCE_URL as SHILLER_URL, fetch_shiller
from tfm.sources.french import SOURCE_URL as FRENCH_URL, fetch_french
from tfm.returns import COLUMNS as RETURN_COLUMNS, FORMULAS, WARNINGS as RETURN_WARNINGS, build_return_components
from tfm.simulation import STRATEGIES
from tfm.sensitivity import sensitivity_scenarios
from tfm.comparators import BEAR_STRATEGIES
from tfm.volatility import SIMPLE_STRATEGIES
from tfm.features import FEATURE_COLUMNS

# Ventana fijada por el diseño del TFM; la evaluación posterior sigue deshabilitada.
START, END = "1927-01", "1989-12"


def project_root() -> Path:
    """Localizar el proyecto al ejecutar desde su raíz o desde notebooks/."""
    here = Path.cwd().resolve()
    for candidate in (here, here.parent):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src/tfm").is_dir():
            return candidate
    raise ValueError("Abre el notebook desde la raíz del proyecto o desde notebooks/.")



def _simulation_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "baseline_simulations.parquet", processed / "baseline_simulations.json"


def _sensitivity_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "baseline_sensitivity.parquet", processed / "baseline_sensitivity.json"


def _bear_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "bear_filter_simulations.parquet", processed / "bear_filter_simulations.json"


def _simple_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "simple_comparisons.parquet", processed / "simple_comparisons.json"


def _label_paths(processed: Path) -> tuple[Path, Path]:
    return processed / "labelled_signals.parquet", processed / "labelled_signals.json"


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
            raise ValueError(f"Ya existe el original {raw}. Ejecuta sin indicar file para reutilizarlo; no se ha sustituido.")
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


def prepare_shiller_data(root: Path, *, file: str | Path | None = None, history_start: str = "1924-12") -> dict:
    raw = root / "data/raw/shiller.xls"
    selected = _original(raw, file)
    content, acquisition = fetch_shiller(url=SHILLER_URL, file=selected)
    table, report = normalize_shiller(content, history_start=history_start)
    if report["status"] != "passed":
        errors = ", ".join(f"{key}: {value}" for key, value in report["error_counts"].items() if value)
        raise ValueError(f"No se han preparado los datos de Shiller ({errors}). Revisa el original; no se han rellenado valores.")
    _save_original(raw, content, {"source": "shiller", "url": SHILLER_URL,
                                  "acquisition": acquisition})
    processed = root / "data/processed"
    return _publish(table, processed / "shiller_monthly.parquet",
                    report,
                    dependents=(processed / "monthly_features.parquet", processed / "monthly_features.json",
                                processed / "shiller_signals.parquet", processed / "shiller_signals.json",
                                processed / "monthly_return_components.parquet", processed / "monthly_return_components.json",
                                *_simulation_paths(processed), *_sensitivity_paths(processed), *_bear_paths(processed), *_simple_paths(processed), *_label_paths(processed)))


def load_monthly(root: Path) -> pd.DataFrame:
    path = root / "data/processed/shiller_monthly.parquet"
    try:
        report = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        table = pd.read_parquet(path)
    except FileNotFoundError as exc:
        raise ValueError("Faltan datos de Shiller preparados. Ejecuta primero el notebook 01.") from exc
    if not isinstance(report, dict):
        raise ValueError("El resumen de Shiller no es válido. Vuelve a preparar los datos.")
    history_start = report.get("interval", {}).get("history_start")
    preparation_window(history_start)
    months = pd.period_range(history_start, END, freq="M").astype(str).tolist()
    start = START
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


def calculate_signals(root: Path) -> dict:
    signals = build_price_signals(load_monthly(root))
    start, end = START, END
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
               "warnings": WARNINGS}
    return _publish(signals, root / "data/processed/shiller_signals.parquet", summary,
                    dependents=(*_simulation_paths(root / "data/processed"),
                                *_sensitivity_paths(root / "data/processed"),
                                *_bear_paths(root / "data/processed"),
                                *_simple_paths(root / "data/processed"),
                                *_label_paths(root / "data/processed")))


def prepare_french_data(root: Path, *, file: str | Path | None = None) -> dict:
    raw = root / "data/raw/french_factors.zip"
    content, acquisition = fetch_french(url=FRENCH_URL, file=_original(raw, file))
    start, end = START, END
    table, report = normalize_french_rf(content, start=start, end=end)
    _save_original(raw, content, {"source": "kenneth_french", "url": FRENCH_URL,
                                  "acquisition": acquisition})
    processed = root / "data/processed"
    return _publish(table, processed / "french_rf_monthly.parquet",
                    report,
                    dependents=(processed / "monthly_return_components.parquet",
                                processed / "monthly_return_components.json", *_simulation_paths(processed), *_sensitivity_paths(processed), *_bear_paths(processed), *_simple_paths(processed), *_label_paths(processed)))


def load_french_rf(root: Path) -> tuple[pd.DataFrame, dict]:
    path = root / "data/processed/french_rf_monthly.parquet"
    try:
        report = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        table = pd.read_parquet(path)
    except FileNotFoundError as exc:
        raise ValueError("Falta RF preparado. Ejecuta el notebook 02.") from exc
    if (not isinstance(report, dict) or report.get("status") != "passed"
            or report.get("rows") != len(table) or report.get("output_unit") != "decimal_monthly_return"):
        raise ValueError("RF o su resumen no coinciden; vuelve a preparar French.")
    start, end = START, END
    validate_rf(table, start=start, end=end)
    return table, {**report, "path": str(path)}


def prepare_return_components(root: Path) -> dict:
    monthly = load_monthly(root)
    rf, _ = load_french_rf(root)
    start, end = START, END
    table = build_return_components(monthly, rf, start=start, end=end)
    report = {"status": "passed", "rows": len(table), "first_period": start, "last_period": end,
              "unit": "decimal_monthly_return", "basis": "monthly_mean_price",
              "formulas": FORMULAS,
              "warnings": RETURN_WARNINGS}
    return _publish(table, root / "data/processed/monthly_return_components.parquet", report,
                    dependents=(*_simulation_paths(root / "data/processed"),
                                *_sensitivity_paths(root / "data/processed"),
                                *_bear_paths(root / "data/processed"),
                                *_simple_paths(root / "data/processed"),
                                *_label_paths(root / "data/processed")))


def read_result(root: Path, name: str) -> tuple[pd.DataFrame, dict]:
    """Leer tablas preparadas y comprobar sus meses, estructura y valores."""
    if name == "monthly_features":
        table, summary = _read_table(root, name)
        required = {"asset", "target_period", "decision_period", "price_source_period",
                    "context_source_period", "features_ready", *FEATURE_COLUMNS}
        months = pd.period_range(START, END, freq="M")
        if (summary.get("status") != "passed" or summary.get("feature_columns") != FEATURE_COLUMNS
                or not required <= set(table)
                or table.target_period.tolist() != months.astype(str).tolist()
                or table.decision_period.tolist() != (months - 1).astype(str).tolist()
                or table.price_source_period.tolist() != (months - 1).astype(str).tolist()
                or table.context_source_period.tolist() != (months - 2).astype(str).tolist()
                or not table.asset.eq(INSTRUMENT).all()
                or not pd.api.types.is_bool_dtype(table.features_ready)
                or not table.features_ready.equals(table[FEATURE_COLUMNS].notna().all(axis=1))):
            raise ValueError("Las características no corresponden al diseño actual; ejecuta de nuevo el notebook 07.")
        for column in FEATURE_COLUMNS:
            values = table[column]
            first = values.first_valid_index()
            if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                    or first is None or values.loc[first:].isna().any()
                    or (column != "industry_breadth_12m" and values.isna().any())
                    or not values.dropna().map(math.isfinite).all()):
                raise ValueError("Características inválidas; ejecuta de nuevo el notebook 07.")
        return table, summary
    if name == "simple_comparisons":
        read_result(root, "monthly_return_components")
        read_result(root, "shiller_signals")
        path = root / "data/processed/simple_comparisons.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la comparación conjunta. Ejecuta el notebook 06.") from exc
        months = pd.period_range(START,
                                END, freq="M").astype(str).tolist()
        required = {"strategy", "period", "decision_period", "position", "capital_start", "capital_end", "net_return",
                    "transaction_cost", "borrow_cost", "price_pnl", "dividend_pnl", "cash_interest", "liquidation_cost",
                    "lookback_start_period", "bear_market", "original_momentum_signal", "original_reversal_signal",
                    "estimated_annual_volatility", "volatility_scale", "volatility_price_start_period"}
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("rows") != len(table) or not required <= set(table)
                or len(table) != len(months) * len(SIMPLE_STRATEGIES) or set(table.strategy) != set(SIMPLE_STRATEGIES)
                or any(table.loc[table.strategy.eq(name), "period"].tolist() != months for name in SIMPLE_STRATEGIES)):
            raise ValueError("La comparación conjunta o su resumen no coinciden; ejecuta el notebook 06.")
        numeric = table.drop(columns=["strategy", "period", "decision_period", "lookback_start_period",
                                      "bear_market", "volatility_price_start_period"])
        if (any(not pd.api.types.is_numeric_dtype(numeric[c]) or numeric[c].isna().any()
                or not numeric[c].map(math.isfinite).all() for c in numeric)
                or not pd.api.types.is_bool_dtype(table.bear_market) or table.bear_market.isna().any()
                or table.capital_end.le(0).any() or not table.position.between(-1, 1).all()
                or not table.volatility_scale.between(0, 1).all() or table.estimated_annual_volatility.lt(0).any()):
            raise ValueError("La comparación contiene posiciones o importes inválidos; ejecuta el notebook 06.")
        return table, {**summary, "path": str(path)}
    if name == "bear_filter_simulations":
        read_result(root, "monthly_return_components")
        read_result(root, "shiller_signals")
        path = root / "data/processed/bear_filter_simulations.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la comparación con filtro bajista. Ejecuta el notebook 05.") from exc
        months = pd.period_range(START,
                                END, freq="M").astype(str).tolist()
        required = {"strategy", "period", "decision_period", "position", "capital_start", "capital_end", "net_return",
                    "price_pnl", "dividend_pnl", "cash_interest", "transaction_cost", "borrow_cost", "liquidation_cost",
                    "lookback_start_period", "lookback_start_price", "decision_price", "market_return_24m", "bear_market",
                    "original_momentum_signal", "original_reversal_signal"}
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("rows") != len(table) or not required <= set(table)
                or len(table) != len(months) * len(BEAR_STRATEGIES) or set(table.strategy) != set(BEAR_STRATEGIES)
                or any(table.loc[table.strategy.eq(name), "period"].tolist() != months for name in BEAR_STRATEGIES)):
            raise ValueError("La comparación bajista o su resumen no coinciden; ejecuta el notebook 05.")
        numeric = table.drop(columns=["strategy", "period", "decision_period", "lookback_start_period", "bear_market"])
        if (any(not pd.api.types.is_numeric_dtype(numeric[c]) or numeric[c].isna().any()
                or not numeric[c].map(math.isfinite).all() for c in numeric)
                or not pd.api.types.is_bool_dtype(table.bear_market) or table.bear_market.isna().any()
                or table.capital_end.le(0).any()):
            raise ValueError("La comparación bajista contiene importes inválidos; ejecuta el notebook 05.")
        return table, {**summary, "path": str(path)}
    if name == "baseline_sensitivity":
        read_result(root, "monthly_return_components")
        read_result(root, "shiller_signals")
        path = root / "data/processed/baseline_sensitivity.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la comparación de supuestos. Ejecuta el notebook 04.") from exc
        scenarios = sensitivity_scenarios(summary.get("parameters", summary.get("configuration", {}).get("simulation", {})))
        expected = [(scenario["scenario"], strategy) for scenario in scenarios for strategy in STRATEGIES]
        required = {"scenario", "scenario_label", "changed_assumption", "strategy", "months", "label",
                    "initial_capital", "transaction_cost_rate", "annual_borrow_rate", "include_dividends", "capital_final", "total_return", "annualized_return",
                    "annualized_volatility", "sharpe", "max_drawdown", "annualized_turnover",
                    "transaction_cost_total", "borrow_cost_total", "annualized_return_delta"}
        months = len(pd.period_range(START,
                                     END, freq="M"))
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("scenarios") != scenarios or summary.get("rows") != len(table)
                or not required <= set(table)
                or list(zip(table.scenario, table.strategy)) != expected
                or not table.months.eq(months).all()):
            raise ValueError("La comparación o su resumen no coinciden; ejecuta el notebook 04.")
        for scenario in scenarios:
            rows = table.loc[table.scenario.eq(scenario["scenario"])]
            if any(not rows[key].eq(value).all() for key, value in scenario["parameters"].items()):
                raise ValueError("Los supuestos de la comparación no coinciden; ejecuta el notebook 04.")
        numeric = table.drop(columns=["scenario", "scenario_label", "changed_assumption", "strategy", "label", "include_dividends"])
        for column in numeric:
            values = numeric[column].dropna() if column == "sharpe" else numeric[column]
            if (not pd.api.types.is_numeric_dtype(values) or values.isna().any()
                    or not values.map(math.isfinite).all()):
                raise ValueError("La comparación contiene métricas inválidas; ejecuta el notebook 04.")
        if table.capital_final.le(0).any():
            raise ValueError("La comparación contiene capital no positivo; ejecuta el notebook 04.")
        return table, {**summary, "path": str(path)}
    if name == "baseline_simulations":
        read_result(root, "monthly_return_components")
        read_result(root, "shiller_signals")
        path = root / "data/processed/baseline_simulations.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Falta la simulación básica. Ejecuta el notebook 03.") from exc
        months = pd.period_range(START,
                                END, freq="M").astype(str).tolist()
        required = {"strategy", "period", "decision_period", "position", "capital_start", "capital_end", "net_return",
                    "price_pnl", "dividend_pnl", "cash_interest", "transaction_cost", "borrow_cost", "liquidation_cost"}
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("rows") != len(table) or not required <= set(table)
                or len(table) != len(months) * len(STRATEGIES)
                or set(table.strategy) != set(STRATEGIES)
                or any(table.loc[table.strategy.eq(name), "period"].tolist() != months for name in STRATEGIES)):
            raise ValueError("La simulación o su resumen no coinciden; vuelve a simular.")
        numeric = table.drop(columns=["strategy", "period", "decision_period"])
        if (any(not pd.api.types.is_numeric_dtype(numeric[c]) or not numeric[c].map(math.isfinite).all() for c in numeric)
                or table.capital_end.le(0).any()):
            raise ValueError("La simulación contiene importes inválidos; vuelve a simular.")
        return table, {**summary, "path": str(path)}
    if name == "french_rf_monthly":
        return load_french_rf(root)
    if name == "monthly_return_components":
        load_monthly(root)
        load_french_rf(root)
        path = root / "data/processed/monthly_return_components.parquet"
        try:
            summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            table = pd.read_parquet(path)
        except FileNotFoundError as exc:
            raise ValueError("Faltan componentes de rentabilidad. Ejecuta el notebook 02.") from exc
        months = pd.period_range(START,
                                END, freq="M").astype(str).tolist()
        if (not isinstance(summary, dict) or summary.get("status") != "passed"
                or summary.get("rows") != len(table) or table.columns.tolist() != RETURN_COLUMNS
                or table.period.tolist() != months or summary.get("unit") != "decimal_monthly_return"):
            raise ValueError("Los componentes o su resumen no coinciden; vuelve a prepararlos.")
        numeric = table.drop(columns=["asset", "period", "previous_period"])
        if any(not pd.api.types.is_numeric_dtype(numeric[c]) or pd.api.types.is_bool_dtype(numeric[c])
               or not numeric[c].map(math.isfinite).all() for c in numeric):
            raise ValueError("Los componentes contienen importes inválidos; vuelve a prepararlos.")
        return table, {**summary, "path": str(path)}
    if name == "shiller_monthly":
        table = load_monthly(root)
    elif name == "shiller_signals":
        monthly = load_monthly(root)
        expected = build_price_signals(monthly)
        expected = expected.loc[expected.target_period.between(START, END)].reset_index(drop=True)
        table, summary = _read_table(root, name)
        try:
            pd.testing.assert_frame_equal(table, expected)
        except AssertionError as exc:
            raise ValueError("Las señales no corresponden a los precios preparados; ejecuta el notebook 01.") from exc
        return table, summary
    else:
        raise ValueError("Resultado desconocido")
    _, summary = _read_table(root, name)
    return table, summary


def _read_table(root: Path, name: str) -> tuple[pd.DataFrame, dict]:
    path = root / "data/processed" / f"{name}.parquet"
    try:
        summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        table = pd.read_parquet(path)
    except FileNotFoundError as exc:
        if name == "monthly_features":
            raise ValueError("Faltan las características; ejecuta primero el notebook 07.") from exc
        raise ValueError(f"Falta {name}; ejecuta su notebook de preparación.") from exc
    if not isinstance(summary, dict) or summary.get("rows") != len(table):
        raise ValueError("La tabla y su resumen no coinciden; vuelve a ejecutar su notebook.")
    return table, {**summary, "path": str(path)}


def save_result(root: Path, name: str, table: pd.DataFrame, report: dict) -> dict:
    """Guardar una tabla calculada y sus supuestos, sin configuraciones de entrada."""
    if name not in {"baseline_simulations", "baseline_sensitivity", "bear_filter_simulations", "simple_comparisons", "monthly_features", "labelled_signals"}:
        raise ValueError("Nombre de resultado desconocido")
    return _publish(table, root / "data/processed" / f"{name}.parquet",
                    {**report, "status": "passed", "rows": len(table)},
                    dependents=_label_paths(root / "data/processed") if name == "monthly_features" else ())
