"""Comandos locales del proyecto, sin dependencias adicionales."""

import argparse
import json
from pathlib import Path
import sys

from tfm.pipeline import PipelineError, import_ssga_reference, run_audit_prices, run_buy_and_hold, run_prepare_prices, run_prepare_shiller
from tfm.menu import interactive_menu, show_audit_result, show_simulation_result, show_shiller_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tfm")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-prices", help="Descargar y preparar precios con registro de ejecución")
    prepare.add_argument("--config", type=Path, default=Path("configs/data.toml"))
    prepare.add_argument("--snapshot", type=Path, help="Reutilizar una descarga existente sin acceder a la red")
    simulate = commands.add_parser("simulate-buy-and-hold", help="Simular comprar y mantener sin descargar datos")
    simulate.add_argument("--config", type=Path, default=Path("configs/buy_and_hold.toml"))
    simulate.add_argument("--prepared", type=Path, required=True, help="Directorio de precios preparados")
    simulate.add_argument("--audit", type=Path, help="Directorio de auditoría seleccionado explícitamente")
    audit = commands.add_parser("audit-prices", help="Auditar calendario y, opcionalmente, distribuciones con una referencia explícita")
    audit.add_argument("--config", type=Path, default=Path("configs/audit.toml"))
    audit.add_argument("--prepared", type=Path, required=True)
    audit.add_argument("--reference", type=Path, help="Snapshot SSGA importado; requiere configs/reconciliation.toml")
    reference = commands.add_parser("import-ssga-dividends", help="Archivar y preparar un Excel histórico oficial de distribuciones")
    reference.add_argument("--config", type=Path, default=Path("configs/reconciliation.toml"))
    reference.add_argument("--file", type=Path, required=True, help="Excel oficial descargado desde State Street")
    shiller = commands.add_parser("prepare-shiller", help="Preparar historia mensual de Shiller (desarrollo 1927–1989)")
    shiller.add_argument("--config", type=Path, default=Path("configs/shiller_monthly.toml"))
    origin = shiller.add_mutually_exclusive_group()
    origin.add_argument("--snapshot", type=Path, help="Reutilizar un original archivado sin red")
    origin.add_argument("--file", type=Path, help="Importar un XLS original local sin red")
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        if sys.stdin.isatty():
            return interactive_menu()
        parser.print_help()
        return 0
    args = parser.parse_args(arguments)
    try:
        if args.command == "prepare-shiller":
            run_dir = run_prepare_shiller(args.config, snapshot_dir=args.snapshot, file_path=args.file)
            show_shiller_result(run_dir)
            return 0
        print("Flujo exploratorio anterior de SPY; no corresponde al desarrollo principal 1927–1989.")
        if args.command == "import-ssga-dividends":
            directory = import_ssga_reference(args.config, args.file)
            print(f"Referencia de distribuciones importada: {directory}")
            print("Original conservado; solo se han preparado importes de la ventana de desarrollo.")
            return 0
        if args.command == "audit-prices":
            run_dir = run_audit_prices(args.config, args.prepared, args.reference)
            return 0 if show_audit_result(run_dir) else 1
        if args.command == "simulate-buy-and-hold":
            run_dir = run_buy_and_hold(args.config, args.prepared, args.audit)
            show_simulation_result(run_dir)
            return 0
        run_dir = run_prepare_prices(args.config, args.snapshot)
    except (PipelineError, OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print(f"Ejecución: {run_dir}")
    print(f"Precios preparados: {record['prepared_dir']}")
    return 0
