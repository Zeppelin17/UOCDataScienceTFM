"""Comandos locales del proyecto, sin dependencias adicionales."""

import argparse
from pathlib import Path
import sys

from tfm.menu import interactive_menu, show_project_summary
from tfm.config import DEFAULT_CONFIG, load_config
from tfm.data import prepare_shiller_data, prepare_spy_data, calculate_signals, prepare_french_data, prepare_return_components
from tfm.sources.prices import DownloadError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tfm")
    commands = parser.add_subparsers(dest="command", required=True)
    simple_data = commands.add_parser("prepare-data", help="Preparar Shiller, SPY o RF de French con rutas fijas")
    simple_data.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    simple_data.add_argument("--source", choices=("shiller", "spy", "french"), default="shiller")
    simple_data.add_argument("--file", type=Path, help="Importar XLS de Shiller, ZIP CSV de French o Parquet de Yahoo (con su JSON de procedencia)")
    simple_signals = commands.add_parser("calculate-signals", help="Calcular señales de Shiller sin simular rentabilidades")
    simple_signals.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    components = commands.add_parser("prepare-returns", help="Preparar precio, dividendo aproximado y RF, sin simular estrategias")
    components.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    status = commands.add_parser("status", help="Consultar qué datos y señales están disponibles, sin modificar archivos")
    status.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
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
            filename = {"shiller": "shiller.xls", "spy": "spy.parquet", "french": "french_factors.zip"}[args.source]
            original = settings['root'] / "data/raw" / filename
            print(f"Origen: {args.file if args.file is not None else original if original.exists() else 'descarga de la fuente configurada'}")
            if args.source == "french":
                print("Preparar RF mensual de French. Solo efectivo; no se utiliza su mercado como S&P.")
                result = prepare_french_data(args.config, file=args.file)
                print(f"RF preparado: {result['rows']} meses, {result['first_period']} → {result['last_period']}.")
                print("RF convertido de porcentaje mensual a decimal; 0,20 en origen equivale a 0,002.")
                print("Siguiente paso: prepare-returns, una vez preparados los datos de Shiller.")
            elif args.source == "shiller":
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
        if args.command == "prepare-returns":
            result = prepare_return_components(args.config)
            print(f"Componentes preparados: {result['rows']} meses, {result['first_period']} → {result['last_period']}.")
            print("Precio, dividendo aproximado y RF separados, en decimal mensual; no hay posiciones ni costes aplicados.")
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
    except (DownloadError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operación cancelada.", file=sys.stderr)
        return 130
