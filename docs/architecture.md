# Arquitectura y acuerdos entre módulos

## Responsabilidades

Cada fuente se adapta a un formato común en `preparation`. Las variables se calculan exclusivamente con información disponible. `signals` genera propuestas; `models` añade su evaluación. `backtesting` transforma ambas en resultados usando un motor común. `validation` define las particiones y `evaluation` interpreta sus salidas.

No se introducen interfaces abstractas ni clases genéricas antes de contar con implementaciones concretas. Los acuerdos siguientes describen los datos esperados. Los esquemas implementados de precios y del benchmark se detallan debajo; señales, etiquetas y modelos permanecen previstos.

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

## Coordinación implementada

`tfm.pipeline.run_prepare_prices` coordina los módulos de descarga y preparación; `tfm.cli` expone `python -m tfm prepare-prices`. La lógica de cada etapa permanece en su módulo, para poder reutilizarla desde un notebook o un flujo posterior. No se introduce un framework de workflows.

El coordinador crea un registro por intento bajo `outputs/runs`, copia la configuración y registra sus rutas resueltas. Las fases son `configuration`, `download` o `snapshot_validation`, `preparation` y `completed`. Los estados son `running`, `completed`, `failed` e `interrupted`. Un error conserva el mensaje, tipo, fase y los artefactos ya terminados. Los snapshots y tablas mantienen sus propios manifiestos; el run referencia sus directorios y copia los manifiestos al terminar.

`--snapshot` permite repetir el procesamiento sin red y exige que los parámetros coincidan con la configuración. Las rutas de almacenamiento parten de la raíz deducida de `configs/`, en línea con el adaptador existente. El comando no realiza entrenamiento ni selección de modelos: sus registros de datos se ampliarán cuando existan experimentos financieros. El estado de Git incluye revisión y cambios locales, pero no una copia del código sin commit.

## Protocolo financiero propuesto

[financial_protocol.md](financial_protocol.md) documenta las convenciones propuestas y las decisiones aún abiertas. El benchmark diario de comprar y mantener está implementado; la tabla mensual y las anomalías se incorporarán después. Este documento no convierte `configs/experiment_base.toml` en una configuración ejecutable ni resuelve la financiación de cortos.


## Primer simulador implementado

- `backtesting.engine`: validación de precios y cálculo de una secuencia de exposiciones 0/1 efectivas al cierre, con rentabilidad anterior al rebalanceo, costes y capital. Sin red, persistencia ni generación de señales.
- `backtesting.buy_and_hold`: genera posiciones del benchmark e invoca el motor. Conserva separado qué se compra de cómo se calcula el resultado financiero.
- `evaluation.simulation`: resumen descriptivo de la trayectoria; no entrena ni calcula métricas de selección de modelos.
- `pipeline.run_buy_and_hold`: configuración, política temporal, verificación SHA-256 de la preparación, intervalo inclusivo, simulación y publicación por ejecución. La política se obtiene de la sección validation de experiment_base.toml; no existe aún un evaluador del periodo final.
- `cli` y `menu`: comando simulate-buy-and-hold y selección interactiva de preparaciones; ambas vías llaman al mismo coordinador.

Esquema inicial de equity.parquet: asset, observed_at, adjusted_close, position_after, position_before, asset_return, gross_return, turnover, cost_fraction, net_return, gross_capital, net_capital, cost_amount y drawdown. Los costes monetarios se expresan en unidades del capital inicial normalizado. drawdown es cero o negativo; max_drawdown del resumen es una magnitud positiva.

El registro utiliza las fases configuration, prepared_validation, simulation, publication y completed. Las ejecuciones completadas incluyen las rutas y huellas de equity.parquet y summary.json. Un fallo o Ctrl+C conserva su estado/error y elimina los resultados financieros parciales, manteniendo configuración y procedencia que se hayan registrado. Como en el flujo previo, una terminación forzada o un fallo de almacenamiento puede dejar un registro running. No se sobrescriben ejecuciones ni se modifica la preparación de entrada.


## Auditoría de calendario implementada

`preparation.prices.load_prepared_prices` comparte entre simulación y auditoría la verificación de esquema, calidad, integridad SHA-256 y fechas del manifiesto. `validation.policy` comparte la lectura de la separación desarrollo/final; no modifica las decisiones del protocolo.

`preparation.calendar` compara las sesiones con XNYS durante todo el intervalo solicitado. `pipeline.run_audit_prices` guarda cada intento y sus artefactos. `preparation.audits.load_calendar_audit` verifica el informe seleccionado antes de usarlo en una simulación, exigiendo coincidencia de datos/manifiesto, cobertura, política y método. `preparation.quality` mantiene los cuatro estados independientes y su presentación, con compatibilidad para preparaciones antiguas.

Los artefactos de auditoría y las simulaciones nuevas no sobrescriben preparaciones ni resultados anteriores. No hay migración destructiva: se añaden estados a informes nuevos y el simulador recibe `audit_dir=None` por defecto. La dependencia exchange_calendars se justifica por la cobertura histórica de cierres especiales; sus versiones exactas se registran en lock e informes. La versión inicial solo acredita calendario. El contraste de distribuciones se describe a continuación. Véase [calendar_audit.md](calendar_audit.md).

## Contraste de distribuciones implementado

`sources.ssga` importa y conserva un XLSX elegido explícitamente, valida el formato del emisor y normaliza únicamente las distribuciones SPY de la ventana de desarrollo. `preparation.reconciliation` compara todos los eventos de ambas fuentes en la intersección y separa cobertura de concordancia. No hay capa abstracta de proveedores ni dependencia de un servidor; se añade openpyxl porque la publicación real del emisor es XLSX.

`pipeline.run_audit_prices(..., reference_dir=None)` conserva v1 sin referencia y publica v2 con referencia explícita, manteniendo resultados anteriores. `preparation.audits` acepta ambas versiones, verifica los artefactos y reproduce el contraste v2 antes de permitir adjuntarlo a una simulación. No se certifican cierres o ajustes mediante distribuciones. Una referencia o configuración alterada o discrepancias sin resolver se rechazan. Véase [source_reconciliation.md](source_reconciliation.md).
