"""Lectura común de la separación entre desarrollo y evaluación final."""

from datetime import date, timedelta
from pathlib import Path
import tomllib


def load_development_policy(path: str | Path) -> tuple[bytes, dict]:
    content = Path(path).read_bytes()
    policy = tomllib.loads(content.decode("utf-8"))["validation"]
    end = date.fromisoformat(policy["development_end"])
    start = date.fromisoformat(policy["final_test_start"])
    if end + timedelta(days=1) != start:
        raise ValueError("La política debe separar desarrollo y periodo final sin huecos ni solapamientos")
    return content, {"development_end": end.isoformat(), "final_test_start": start.isoformat()}


def parse_historical_policy(content: bytes) -> dict:
    declared = tomllib.loads(content.decode("utf-8"))["validation"]
    expected = {"development_start": "1927-01-01", "development_end": "1989-12-31",
                "final_test_start": "1990-01-01", "final_test_end": "pending"}
    if declared != expected:
        raise ValueError("Este flujo exige desarrollo 1927–1989 y evaluación desde 1990 aún deshabilitada")
    return declared


def load_historical_policy(path: str | Path) -> tuple[bytes, dict]:
    """Política del estudio mensual, separada de la exploración previa con SPY."""
    content = Path(path).read_bytes()
    return content, parse_historical_policy(content)
