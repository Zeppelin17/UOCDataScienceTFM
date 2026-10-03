# Arquitectura y acuerdos entre módulos

## Responsabilidades

Cada fuente se adapta a un formato común en `preparation`. Las variables se calculan exclusivamente con información disponible. `signals` genera propuestas; `models` añade su evaluación. `backtesting` transforma ambas en resultados usando un motor común. `validation` define las particiones y `evaluation` interpreta sus salidas.

No se introducen interfaces abstractas ni clases genéricas antes de contar con implementaciones concretas. Los acuerdos siguientes describen los datos esperados; no son esquemas ya implementados.

## Contratos de datos previstos

| Tabla | Campos mínimos previstos | Restricción |
|---|---|---|
| Precios | asset, observed_at, price, adjustment, source | Unicidad por activo, fecha y tipo de precio; ajustes explícitos. |
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
