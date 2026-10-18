"""Comandos locales del proyecto, sin dependencias adicionales."""

import argparse
import json
from pathlib import Path
import sys

from tfm.pipeline import PipelineError, import_ssga_reference, run_audit_prices, run_buy_and_hold, run_prepare_prices, run_prepare_shiller, run_shiller_signals
from tfm.menu import interactive_menu, show_project_summary, show_audit_result, show_simulation_result, show_shiller_result, show_shiller_signals_result
from tfm.config import DEFAULT_CONFIG, load_config
from tfm.data import prepare_shiller_data, prepare_spy_data, calculate_signals
from tfm.sources.prices import DownloadError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tfm")
    commands = parser.add_subparsers(dest="command", required=True)
    simple_data = commands.add_parser("prepare-data", help="Preparar Shiller o SPY con configuración única y rutas fijas")
    simple_data.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    simple_data.add_argument("--source", choices=("shiller", "spy"), default="shiller")
    simple_data.add_argument("--file", type=Path, help="Importar un original local si aún no hay uno guardado")
    simple_signals = commands.add_parser("calculate-signals", help="Calcular señales de Shiller sin simular rentabilidades")
    simple_signals.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    status = commands.add_parser("status", help="Consultar qué datos y señales están disponibles, sin modificar archivos")
    status.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
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
    signals = commands.add_parser("build-shiller-signals", help="Generar señales de diagnóstico sobre promedios mensuales, sin simular rentabilidades")
    signals.add_argument("--config", type=Path, default=Path("configs/shiller_signals.toml"))
    signals.add_argument("--prepared", type=Path, required=True, help="Directorio mensual de Shiller preparado")
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        if sys.stdin.isatty():
            return interactive_menu()
        parser.print_help()
        return 0
    args = parser.parse_args(arguments)
    try:
        if args.command == "status":
            settings = load_config(args.config)
            show_project_summary(settings)
            print(f"Carpeta del proyecto: {settings['root']}")
            print("Abre python -m tfm para consultar las primeras filas desde el menú.")
            return 0
        if args.command == "prepare-data":
            settings = load_config(args.config)
            filename = "shiller.xls" if args.source == "shiller" else "spy.parquet"
            original = settings['root'] / "data/raw" / filename
            print(f"Origen: {args.file if args.file is not None else original if original.exists() else 'descarga de la fuente configurada'}")
            if args.source == "shiller":
                print("Preparar datos mensuales de Shiller. Se reutiliza el original local; si falta, se importa o descarga.")
                print(f"Periodo preparado: {settings['shiller']['history_start']} → {settings['validation']['development_end'][:7]}.")
                result = prepare_shiller_data(args.config, file=args.file)
                print(f"Datos preparados: {result['rows']} meses, {result['first_period']} → {result['last_period']}.")
                print("Sin meses ausentes ni duplicados. Son precios medios mensuales, no precios de ejecución.")
                print(f"Siguiente paso: python -m tfm calculate-signals --config \"{args.config}\"")
            else:
                print("Preparar datos diarios de SPY de Yahoo Finance. Se mantienen separados de Shiller.")
                print(f"Periodo solicitado: {settings['spy']['start']} → {settings['spy']['end']} (fin exclusivo).")
                result = prepare_spy_data(args.config, file=args.file)
                print(f"Datos preparados: {result['rows']} sesiones, {result['first_session'][:10]} → {result['last_session'][:10]}.")
                print("Controles de estructura superados; calendario y exactitud financiera no certificados.")
                print("La utilización definitiva de SPY en el estudio sigue pendiente.")
            print(f"Archivo: {result['path']}")
            return 0
        if args.command == "calculate-signals":
            result = calculate_signals(args.config)
            print(f"Señales de Shiller calculadas: {result['rows']} meses objetivo, {result['both_rules_available']} con ambas señales disponibles.")
            missing = result['missing_momentum_targets']
            if missing:
                print(f"Sin historia suficiente para momentum: {', '.join(missing)}.")
            print("Señales sobre promedios mensuales, sin simulación de rentabilidades ni entrenamiento de modelos.")
            print(f"Archivo: {result['path']}")
            return 0
        if args.command == "build-shiller-signals":
            run_dir = run_shiller_signals(args.config, args.prepared)
            show_shiller_signals_result(run_dir)
            return 0
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
    except (PipelineError, DownloadError, OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operación cancelada.", file=sys.stderr)
        return 130
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print(f"Ejecución: {run_dir}")
    print(f"Precios preparados: {record['prepared_dir']}")
    return 0
