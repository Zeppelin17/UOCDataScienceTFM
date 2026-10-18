"""Comandos locales del proyecto, sin dependencias adicionales."""

import argparse
from pathlib import Path
import sys

from tfm.menu import interactive_menu, show_project_summary
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
    except (DownloadError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operación cancelada.", file=sys.stderr)
        return 130
