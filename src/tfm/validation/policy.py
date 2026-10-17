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
