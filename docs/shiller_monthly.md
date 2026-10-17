# Historia mensual de Shiller: estudio principal 1.B

## Decisión y alcance

Se siguen los periodos recomendados por la guía local del TFM: desarrollo **1927–1989** y evaluación desde **1990** hasta un corte de 2026 aún por fijar. Este incremento prepara exclusivamente datos, sin estrategias, etiquetas, modelos, retornos ni simulaciones. La fuente es la serie histórica S&P Composite publicada por Robert J. Shiller, no participaciones de SPY ni una serie idéntica al S&P 500 moderno durante toda su historia.

Shiller es una candidata para el análisis mensual de historia larga propuesto en la guía. **La idoneidad de las rentabilidades y la ejecución para un backtest queda pendiente del protocolo financiero.** Importar una tabla no resuelve esa decisión. La memoria todavía contiene el planteamiento SPY/desarrollo hasta 2020 y deberá actualizarse expresamente antes de presentar el nuevo diseño como documentado.

La fuente oficial es https://shillerdata.com/ y su enlace `ie_data.xls`. La configuración conserva el enlace publicado al revisarlo el 17/10/2026. Si cambia la ubicación, debe actualizarse explícitamente el TOML con el enlace oficial; no hay búsqueda silenciosa de espejos o sustitución de fuente. Cada adquisición registra el enlace concreto y su destino resuelto, tiempo UTC y SHA-256.

## Semántica y columnas

El archivo original contiene, entre otros campos, precios medios, dividendos y beneficios interpolados y columnas de rentabilidad futura a diez años. La tabla preparada admite **solo Date, P y D** del libro, más identificadores y el papel de cada fila:

| Campo | Significado |
|---|---|
| `asset` | `SHILLER_SP_COMPOSITE`, distinto de SPY. |
| `period` | Mes `YYYY-MM`; no fecha de orden ni instante de disponibilidad. |
| `price_monthly_mean` | P nominal: promedio mensual de cierres diarios, en puntos del índice. |
| `dividend_annualized` | D anualizado e interpolado, en puntos del índice; se conserva sin dividir por doce. |
| `sample_role` | `history` antes de 1927, `development` desde 1927 hasta 1989. |
| `source` | `shiller`. |

No se producen `adjusted_close`, precios de ejecución o retornos. D no se interpreta como reparto mensual observado ni como variable conocida en cada fecha. Incluso excluyendo columnas futuras explícitas, las interpolaciones y revisiones requieren estudiar su disponibilidad antes de utilizar D como predictor. El manifiesto indica disponibilidad desconocida y ausencia de garantías point-in-time. No se trata una fecha de observación como fecha de publicación.

La documentación del autor explica precios medios e interpolación: https://shillerdata.com/. El lector valida la hoja `Data` y la cabecera `Date, P, D`. Se lee directamente XLS con **xlrd**, sin ejecutar fórmulas, convertir el libro o incorporar sus columnas auxiliares. HTTPS mantiene la verificación de certificado y nombre del servidor, añadiendo el bundle CA de certifi a la confianza predeterminada de Python; no se utiliza verify=False. certifi ya estaba instalado por otras dependencias y se declara ahora explícitamente por su uso directo.

## Ventana y protecciones

`configs/shiller_monthly.toml` define el origen y la historia previa. `configs/historical_policy.toml` fija desarrollo 1927–1989 y evaluación desde 1990. El cargador mensual exige esos límites y mantiene la evaluación deshabilitada (`final_test_end=pending`); cambiar al TOML antiguo o ampliar el desarrollo a 1990 produce un error antes de adquirir o preparar datos.

Por defecto se publican **1926-01 a 1989-12**, ambos inclusive: 12 meses de historia previa y 756 de desarrollo. Puede ampliarse la historia previa, hasta 1871, si una futura variable necesita ventanas más largas. Esto no permite ampliar el desarrollo. Los 756 meses no son necesariamente 756 ejemplos de entrenamiento ni observaciones independientes: faltarán resultados o antecedentes según las etiquetas y ventanas. Una etiqueta que requiera resultados de 1990 quedará fuera del entrenamiento inicial.

El XLS original completo queda aislado en `data/raw/`, excluido de Git; puede incluir datos de evaluación y columnas de resultados futuros. Solo se consultan las etiquetas mensuales fuera de la ventana, para registrar cobertura del original; no se interpretan los importes P/D fuera de ella, ni columnas de CPI, CAPE, beneficios o rendimientos futuros de ninguna fecha. El test del lector rechaza cualquier acceso a esos campos.

La fecha numérica del Excel es `YYYY.MM`, no una fracción de año. Por ejemplo, `1926.10` llega como número `1926.1` y debe convertirse en octubre. Se comprueban meses válidos, cobertura mensual continua, duplicados, ausentes, precio positivo, dividendo no negativo y valores numéricos finitos. No se rellenan meses, se eliminan duplicados ni se imputan importes.

El control `passed` significa **estructura y cobertura mensual aprobadas**, no exactitud externa o viabilidad de negociación. La cobertura global del archivo incluye el mes parcial en curso; no se da por completo para una futura evaluación. El incremento actual no usa importes posteriores a 1989.

## Comandos

Desde la raíz, con el entorno virtual activado, descargar y preparar:

```bash
python -m tfm prepare-shiller
```

Importar un XLS oficial que ya tengas, conservando exactamente sus bytes:

```bash
python -m tfm prepare-shiller --file /ruta/ie_data.xls
```

Repetir desde un original archivado, sin red:

```bash
python -m tfm prepare-shiller --snapshot /ruta/al/snapshot
```

`--file` y `--snapshot` son excluyentes. `--config` permite indicar la ubicación de `configs/shiller_monthly.toml`; las rutas declaradas se resuelven desde la raíz deducida de su carpeta `configs`, como en los demás flujos.

En `python -m tfm`, la **opción 9** permite descargar (`D`), importar un XLS local (`F`) o seleccionar un original archivado por número. No se elige el más reciente automáticamente. La opción 3 consulta los registros. Las opciones previas de SPY se identifican como exploración anterior. La configuración mensual debe estar junto al TOML de datos activo; cambiar ese TOML mediante la opción 5 solo cambia la configuración SPY.

## Artefactos y responsabilidades

- `sources/shiller.py`: archivo del original HTTPS o importación local y lectura de snapshot verificada. Limita tamaño a 10 MiB y exige XLS binario y enlace oficial. Importar un archivo local registra su procedencia declarada, sin afirmar una descarga autenticada del emisor.
- `preparation/shiller.py`: selección explícita de campos y ventana, calidad y publicación del contrato mensual. Incluye un lector verificado separado del lector de precios SPY.
- `validation/policy.py`: añade la política histórica sin alterar la lectura usada por los flujos anteriores.
- `pipeline.run_prepare_shiller`: configura, registra la adquisición/preparación y copia la procedencia. CLI y menú llaman al mismo coordinador.

Cada snapshot nuevo se guarda bajo `data/raw/shiller/SHILLER_SP_COMPOSITE/<id>/`, con `original.xls` y `manifest.json`. El estado `archived` solo acredita que se ha conservado el archivo, no su calidad financiera. Una preparación nueva se guarda en `data/processed/shiller_monthly/<id>/`, con:

- `monthly.parquet`, únicamente si supera la calidad.
- `manifest.json` y `quality_report.json`, con esquema/normalización, intervalo, roles, limitaciones, versiones y huellas.
- `source_manifest.json` y `validation_policy.toml`, conservados con sus huellas.

`load_shiller_monthly` verifica esquema, integridad, política exacta, columnas permitidas, tipos, valores, orden y cobertura. Una tabla diaria SPY no es compatible; tampoco se utiliza el motor diario actual para procesar estos promedios.

Cada intento tiene un registro en `outputs/runs/<id>/`: estados `running`, `completed`, `failed` o `interrupted`; fases de configuración, descarga/importación/verificación de snapshot y preparación. Se guardan configuración, política, versiones, estado Git y procedencia. Un problema de calidad conserva informe y manifiesto fallidos sin Parquet; errores de formato o integridad bloquean la preparación. Los fallos de escritura limpian el directorio parcial. Se conservan los originales ya archivados y nunca se sobrescriben resultados. Como en los flujos existentes, una terminación forzada o fallo de almacenamiento puede dejar un registro `running`.

## Compatibilidad y exposición previa

No se cambian `configs/experiment_base.toml`, los archivos originales, informes ni resultados previos. Esos TOML conservan el protocolo exploratorio anterior; **no gobiernan el estudio principal nuevo**. Las discrepancias de distribuciones SPY siguen documentadas, sin ser convertidas en comprobaciones superadas.

Ya se examinó parte de 1993–2020 para construir la herramienta anterior. El nuevo periodo 1990–2026 podrá evaluarse cronológicamente con un procedimiento fijado a partir del desarrollo anterior a 1990, pero no se describirá todo él como nunca consultado. Este incremento no usa los resultados conocidos para seleccionar variables, hiperparámetros o reglas.

## Verificación real

El archivo revisado el 17/10/2026 (`SHA-256 98a54927942e842ec07ffe73000998e793953708c345b6b27bb363e9ada8366a`) contiene etiquetas mensuales desde 1871-01 hasta 2026-10. La preparación real produce 768 filas entre 1926-01 y 1989-12: 12 de historia y 756 de desarrollo, sin meses ausentes/duplicados ni errores estructurales. No se interpreta esa comprobación como validación económica. El recorrido se verifica también con importación local y repetición sin red; las pruebas esenciales cubren selección temporal/de columnas, lectura de octubre, integridad y errores bloqueantes.
