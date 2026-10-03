"""Comandos locales del proyecto, sin dependencias adicionales."""

import argparse
import json
from pathlib import Path
import sys

from tfm.pipeline import PipelineError, run_prepare_prices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tfm")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-prices", help="Descargar y preparar precios con registro de ejecución")
    prepare.add_argument("--config", type=Path, default=Path("configs/data.toml"))
    prepare.add_argument("--snapshot", type=Path, help="Reutilizar una descarga existente sin acceder a la red")
    args = parser.parse_args(argv)
    try:
        run_dir = run_prepare_prices(args.config, args.snapshot)
    except (PipelineError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print(f"Ejecución: {run_dir}")
    print(f"Precios preparados: {record['prepared_dir']}")
    return 0
