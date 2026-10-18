"""Configuración única del estudio; sin registros ni configuraciones por tarea."""

from datetime import date
from pathlib import Path
import tomllib

from tfm.preparation.shiller import preparation_window
from tfm.sources.shiller import validate_source_url


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs/estudio.toml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    path = Path(path).expanduser().resolve()
    content = path.read_bytes()
    config = tomllib.loads(content.decode("utf-8"))
    try:
        if not isinstance(config.get("spy"), dict) or set(config["spy"]) != {"start", "end"}:
            raise ValueError("La sección spy solo admite start y end; el activo está fijado en SPY")
        validate_source_url(config["shiller"]["url"])
        preparation_window(config["shiller"]["history_start"], content)
        if config["signals"] != {"basis": "monthly_mean_price", "momentum_non_positive": "cash"}:
            raise ValueError("Las señales requieren promedios mensuales y momentum no positivo en efectivo")
        start, end = (date.fromisoformat(config["spy"][key]) for key in ("start", "end"))
        if start >= end:
            raise ValueError("El inicio de SPY debe preceder a su fin exclusivo")
    except (KeyError, TypeError) as exc:
        raise ValueError("Configuración incompleta; revisa las secciones de configs/estudio.toml") from exc
    return {**config, "root": path.parent.parent, "policy_bytes": content}
