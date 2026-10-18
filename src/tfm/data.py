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


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _publish(table: pd.DataFrame, path: Path, summary: dict, *, dependents: tuple[Path, ...] = ()) -> dict:
    """Preparar ambos archivos antes de sustituir una salida existente.

    Sin el resumen no se acepta una tabla como terminada. Los dependientes se
    invalidan antes de sustituir su entrada; no se necesita un registro de runs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    report_path = path.with_suffix(".json")
    temporary = path.with_suffix(".parquet.tmp")
    temporary_report = path.with_suffix(".json.tmp")
    try:
        table.to_parquet(temporary, index=False)
        _json(temporary_report, summary)
        report_path.unlink(missing_ok=True)
        for dependent in dependents:
            dependent.unlink(missing_ok=True)
        temporary.replace(path)
        temporary_report.replace(report_path)
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
                    dependents=(processed / "shiller_signals.parquet", processed / "shiller_signals.json"))


def load_monthly(settings: dict) -> pd.DataFrame:
    path = settings["root"] / "data/processed/shiller_monthly.parquet"
    try:
        report = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        table = pd.read_parquet(path)
    except FileNotFoundError as exc:
        raise ValueError("Faltan datos de Shiller preparados. Ejecuta primero prepare-data.") from exc
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
    return _publish(signals, settings["root"] / "data/processed/shiller_signals.parquet", summary)


def prepare_spy_data(config: str | Path = DEFAULT_CONFIG, *, file: str | Path | None = None) -> dict:
    settings = load_config(config)
    root = settings["root"]
    raw = root / "data/raw/spy.parquet"
    selected = _original(raw, file)
    parameters = {"tickers": "SPY", **settings["spy"], "interval": "1d", "auto_adjust": False,
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
