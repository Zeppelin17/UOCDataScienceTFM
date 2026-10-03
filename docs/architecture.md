# Arquitectura y acuerdos entre módulos

## Responsabilidades

Cada fuente se adapta a un formato común en `preparation`. Las variables se calculan exclusivamente con información disponible. `signals` genera propuestas; `models` añade su evaluación. `backtesting` transforma ambas en resultados usando un motor común. `validation` define las particiones y `evaluation` interpreta sus salidas.

No se introducen interfaces abstractas ni clases genéricas antes de contar con implementaciones concretas. Los acuerdos siguientes describen los datos esperados. El esquema de precios implementado se detalla al final; el resto permanece previsto.

## Contratos de datos previstos

| Tabla | Campos mínimos previstos | Restricción |
|---|---|---|
| Precios | asset, observed_at, open, high, low, close, adjusted_close, volume, dividends, stock_splits, source | Una fila por activo y sesión; cierre y cierre ajustado separados. |
| Indicadores | series_id, observed_at, available_at, value, vintage | Incorporar revisiones y disponibilidad cuando la fuente lo permita. |
| Variables | asset, decision_at, feature_set_version, variables | Solo información disponible en decision_at. |
| Señales | signal_id, strategy, asset, decision_at, side, exposure | Identificador único y regla original reproducible. |
| Etiquetas | signal_id, outcome_start, outcome_end, label, return | Resultado futuro separado de las variables. |
| Predicciones | run_id, signal_id, probability, accepted | Salida compatible con el simulador, independiente del algoritmo. |
| Resultados | run_id, date, position, gross_return, costs, net_return | Misma política de ejecución para comparaciones equivalentes. |

Una ampliación del esquema deberá documentarse. Los conjuntos ya utilizados por un experimento no se sobrescribirán silenciosamente. Registrar la versión del conjunto y del código permite reconstruir las ejecuciones.

## Integración temporal

La fecha que describe un indicador no equivale necesariamente a su publicación. Las uniones se harán por información disponible al decidir. No se utilizarán revisiones posteriores como si fueran conocidas en el pasado. Si faltan fechas de publicación o vintages, la limitación y el tratamiento se documentarán antes de usar la serie.

## Ejecuciones

Cada ejecución tendrá un directorio propio bajo `outputs/runs/<run_id>/` con configuración efectiva, manifiesto de datos, particiones, predicciones y métricas. Se registrarán también las configuraciones fallidas o descartadas. El registro completo será necesario para evaluar la búsqueda entre alternativas.

La separación del periodo final deberá comprobarse en el código de entrenamiento y selección; declararla en TOML no constituye aún una protección implementada.

## Errores y seguridad

Descargas fallidas, duplicados y cobertura insuficiente deberán generar errores explícitos o informes de calidad. No se imputarán silenciosamente datos financieros. Las credenciales permanecerán fuera del repositorio y se respetarán las condiciones de redistribución de las fuentes.

## Decisiones pendientes

- Posición del momentum cuando el retorno no es positivo: efectivo o corto.
- Horizonte y definición de las etiquetas.
- Fecha, precio y mecanismo de ejecución.
- Dividendos, remuneración del efectivo, cortos, exposición y apalancamiento.
- Modelo y escenarios de costes.
- Fuentes, muestra definitiva y fecha de corte de evaluación final.
- Definición exacta de los filtros publicados de referencia.
- Método concreto de validación, purga y controles de sobreajuste.

## Alcance inicial

Procesamiento local por lotes. No se requieren API HTTP, servidor ni base de datos externa. Los módulos crecerán a medida que se complete cada incremento, conservando las responsabilidades y las tablas comunes.

## Preparación de precios implementada

`tfm.preparation.prices.prepare_prices(snapshot_dir, processed_root)` verifica la huella SHA-256 de la descarga y su número de filas, cambia nombres de columnas y ordena las sesiones. Se usa una tabla ancha: cada sesión conserva sus precios OHLC, cierre ajustado, volumen y eventos en columnas separadas. `observed_at` representa la fecha de sesión, sin zona horaria; no representa una fecha de publicación ni un instante de decisión.

Versión 1 del esquema: `asset`, `observed_at`, `open`, `high`, `low`, `close`, `adjusted_close`, `volume`, `dividends`, `stock_splits`, `source`. Para este primer adaptador, `asset=SPY` y `source=yahoo`. No se imputan valores, eliminan duplicados, recalculan ajustes ni convierten datos a frecuencia mensual. No se exige que el cierre ajustado esté entre el máximo y el mínimo, porque utiliza otra escala.

Cada preparación genera un directorio nuevo bajo `<processed_root>/prices/<preparation_id>/`. Un resultado válido contiene `prices.parquet`, `quality_report.json` y `manifest.json`, con la procedencia y la huella de la tabla preparada. Un resultado con errores de calidad conserva informe y manifiesto, sin publicar Parquet, y lanza `PriceQualityError`; su atributo `report_path` permite localizar el informe. Los errores de integridad o estructura se rechazan antes de crear el resultado. Un fallo de escritura elimina el directorio parcial.

Los controles bloqueantes comprueban datos vacíos, fechas ausentes, duplicadas o con horas, valores ausentes o infinitos, precios no positivos, volumen y eventos negativos, coherencia OHLC y fechas fuera del intervalo solicitado. No certifican la exactitud del proveedor ni detectan todavía sesiones ausentes mediante un calendario bursátil. La separación general del periodo final se implementará en el flujo de experimentos.
