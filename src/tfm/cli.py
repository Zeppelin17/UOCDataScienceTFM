"""Comandos locales del proyecto, sin dependencias adicionales."""

import argparse
import json
from pathlib import Path
import sys

from tfm.pipeline import PipelineError, run_buy_and_hold, run_prepare_prices
from tfm.menu import interactive_menu, show_simulation_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tfm")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-prices", help="Descargar y preparar precios con registro de ejecución")
    prepare.add_argument("--config", type=Path, default=Path("configs/data.toml"))
    prepare.add_argument("--snapshot", type=Path, help="Reutilizar una descarga existente sin acceder a la red")
    simulate = commands.add_parser("simulate-buy-and-hold", help="Simular comprar y mantener sin descargar datos")
    simulate.add_argument("--config", type=Path, default=Path("configs/buy_and_hold.toml"))
    simulate.add_argument("--prepared", type=Path, required=True, help="Directorio de precios preparados")
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        if sys.stdin.isatty():
            return interactive_menu()
        parser.print_help()
        return 0
    args = parser.parse_args(arguments)
    try:
        if args.command == "simulate-buy-and-hold":
            run_dir = run_buy_and_hold(args.config, args.prepared)
            show_simulation_result(run_dir)
            return 0
        run_dir = run_prepare_prices(args.config, args.snapshot)
    except (PipelineError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print(f"Ejecución: {run_dir}")
    print(f"Precios preparados: {record['prepared_dir']}")
    return 0
