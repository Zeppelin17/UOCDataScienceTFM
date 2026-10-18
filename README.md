# ¿Invertir o esperar?

Proyecto de programación del TFM de Ciencia de Datos: evaluación de filtros de aprendizaje automático para reglas de momentum y reversión sobre el S&P 500.

## Estado del proyecto

El estudio principal sigue la guía 1.B: desarrollo mensual en 1927–1989 y evaluación desde 1990 hasta un corte de 2026 pendiente de fijar. Ya se puede descargar o importar el Excel de Shiller y preparar únicamente 1926–1989, distinguiendo historia previa y desarrollo. Ya se pueden generar señales de momentum y reversión sobre los promedios mensuales; todavía no se simulan sus rentabilidades ni se entrenan modelos.

La exploración previa con SPY conserva descarga, preparación, simulador diario, auditoría de calendario y contraste de distribuciones. Sus resultados y configuraciones se mantienen como planteamiento anterior, separado de la historia mensual. Véase [la fuente y el alcance del nuevo flujo](docs/shiller_monthly.md).

El [protocolo mensual](docs/monthly_protocol.md) documenta las reglas y las decisiones pendientes antes de simular. Se mantiene Shiller como fuente y se distingue el cálculo de señales de una reproducción de operaciones ejecutables.

## Arquitectura

El proyecto sigue un proceso incremental organizado según CRISP-DM: comprensión del problema, comprensión y preparación de datos, modelado, evaluación y entrega reproducible.

```text
Fuentes → originales → preparación → variables → reglas → señales
                                              ↓          ↓
                                          modelo ← etiquetas
                                              ↓
                                         decisiones
                                              ↓
                        simulador común → evaluación → gráficos
```

Las reglas originales generan la dirección de las señales. El meta-modelo decide si aceptarlas. Todas las estrategias utilizan el mismo simulador para comparar ejecución, posiciones y costes con criterios consistentes.

## Estructura

```text
configs/                 Configuración de datos y experimentos
src/tfm/
  cli.py                 Comandos locales
  pipeline.py            Coordinación y registro de ejecuciones
  sources/               Descarga y procedencia de datos
  preparation/           Calidad, normalización e integración temporal
  features/              Variables disponibles en cada decisión
  signals/               Reglas originales y filtros de referencia
  labels/                Resultados futuros de las señales para entrenar
  models/                Entrenamiento y predicción del meta-modelo
  validation/            Particiones temporales y registro de pruebas
  backtesting/           Posiciones, ejecución, costes y retornos
  evaluation/            Métricas, controles de sobreajuste e interpretación
notebooks/               Exploración y explicación del análisis
tests/                   Verificaciones temporales y financieras
data/raw/                Copias originales de las fuentes
data/processed/          Tablas limpias y normalizadas
data/datasets/           Conjuntos de variables y etiquetas
outputs/runs/            Configuración, predicciones y resultados por ejecución
docs/                    Contratos de datos y plan incremental
```

Los módulos reutilizables viven en `src/tfm`. Los cuadernos llaman a esos módulos; no deben ser el único lugar donde exista lógica necesaria para reproducir el estudio.

## Datos y reproducibilidad

Se utiliza pandas para el procesamiento y Parquet para persistir tablas. Las nuevas dependencias se añadirán cuando una función las necesite. DuckDB podrá incorporarse si las consultas SQL lo justifican.

- Conservar originales y registrar fuente, fecha de descarga y ajustes.
- Distinguir fecha observada, fecha disponible, decisión y ejecución.
- Mantener etiquetas futuras separadas de las variables explicativas.
- Identificar el activo incluso cuando solo se estudie SPY.
- Registrar configuraciones, versiones, semillas y particiones por ejecución.
- No sobrescribir resultados de experimentos anteriores.

El bloque principal de desarrollo es 1927–1989; 1926 se conserva inicialmente como historia previa. Desde 1990 comienza la evaluación, cuyo corte final permanece pendiente. La configuración histórica impide preparar importes desde 1990. Ya se consultó parte de 1993–2020 bajo el planteamiento anterior: no se presenta todo el nuevo periodo de evaluación como nunca examinado. Los resultados de evaluación no se utilizarán para elegir variables, modelos o filtros.

## Entorno local

Se propone Python 3.11 o posterior. Para crear un entorno aislado:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

La instalación editable utiliza setuptools como herramienta de construcción. pandas procesa las tablas, PyArrow permite persistir Parquet, exchange_calendars aporta las reglas históricas de sesiones, openpyxl lee el Excel oficial de distribuciones, xlrd lee el XLS original de Shiller y el extra `dev` incorpora pytest. yfinance obtiene la respuesta de Yahoo Finance. Para comprobar que el paquete se importa tras instalarlo:

```bash
python -c "import tfm; print(tfm.__version__)"
```

## Desarrollo incremental

1. Primera fuente y reconstrucción de tablas desde originales.
2. Simulador básico con comprar y mantener y costes (implementado).
3. Señales de momentum y reversión sobre promedios de Shiller (implementado); simulación mensual pendiente.
4. Variables de entorno, integración de fuentes y filtros sencillos.
5. Etiquetas, particiones temporales y registro de configuraciones.
6. Primer meta-modelo sencillo y predicciones fuera de muestra.
7. Alternativas justificadas, SHAP y controles DSR/PBO.
8. Configuración fijada, evaluación final y exportación de resultados.

Consulta `docs/architecture.md` para los contratos y las decisiones pendientes. El [protocolo financiero anterior](docs/financial_protocol.md) describe el primer simulador diario de SPY; el [protocolo mensual propuesto](docs/monthly_protocol.md) prepara el siguiente incremento.

La CLI dispone de un menú interactivo. Su alcance y ampliaciones están descritos en [el plan de la CLI](docs/cli_plan.md).

## Verificación

Los tests se añadirán con cada comportamiento implementado. Priorizarán disponibilidad temporal de datos, ventanas de señales, separación de etiquetas, ejecución y costes, purga de particiones cuando corresponda y un recorrido completo con datos pequeños calculables a mano.

El framework de tests es pytest. Se ejecuta con `python -m pytest -q`. Se mantienen tests esenciales de descarga, preparación y flujo completo; el simulador tiene pruebas esenciales de cálculo, protección temporal y recorrido por CLI y menú.

### Dependencias reproducibles

`requirements-lock.txt` registra las versiones verificadas con Python 3.14 en macOS. Para reproducir ese entorno, instala primero `python -m pip install -r requirements-lock.txt` y después `python -m pip install --no-deps -e .`. En otra versión de Python o plataforma, resuelve las dependencias de `pyproject.toml` y valida antes de renovar este archivo.

## Fuente de precios de SPY (exploración anterior)

Yahoo Finance para SPY, limitado inicialmente a 29/01/1993–31/12/2020. Los parámetros explícitos están en `configs/data.toml`. Consulta [la ficha de fuente](docs/data_sources.md) para la comprobación realizada, el tratamiento de ajustes y las verificaciones pendientes. El adaptador de descarga está implementado; la normalización y el informe de calidad también están disponibles.

## Descargar un snapshot de precios

Desde la raíz del repositorio, con el entorno virtual activado:

```bash
python -c 'from tfm.sources.prices import download_prices; print(download_prices("configs/data.toml"))'
```

Cada ejecución descarga el periodo configurado y crea un directorio nuevo en `data/raw/yahoo/SPY/<snapshot_id>/`, excluido de Git:

- `prices.parquet`: tabla devuelta por yfinance, con fechas, precios, cierre ajustado y eventos, sin normalización propia.
- `manifest.json`: parámetros efectivos, configuración, tiempos UTC, versiones de bibliotecas, cobertura y SHA-256 del Parquet.

Los snapshots anteriores no se sobrescriben. Una respuesta vacía, columnas incompatibles o fechas fuera del intervalo generan un error. Si falla la escritura, se elimina el directorio parcial. El manifiesto identifica una descarga terminada. Esto no sustituye el informe de calidad: los valores ausentes, duplicados y la coherencia económica se revisarán en `preparation`.

La copia conserva la salida de yfinance, no el payload HTTP original de Yahoo. Tampoco representa una versión conocida en la fecha histórica. El adaptador está limitado por ahora a SPY diario y exige los parámetros documentados. No impone por sí solo un bloqueo general del periodo final; utiliza el intervalo de la configuración.

Verificación de este incremento: nueve tests sin red y descarga real de 7.033 sesiones entre 29/01/1993 y 31/12/2020. El contraste numérico con otra fuente sigue pendiente.

## Preparar los precios descargados

Sustituye `RUTA_DEL_SNAPSHOT` por el directorio devuelto por la descarga:

```bash
python -c 'from tfm.preparation.prices import prepare_prices; print(prepare_prices("RUTA_DEL_SNAPSHOT", "data/processed"))'
```

Se verifica la integridad del original y se guardan una tabla con columnas normalizadas, su informe de calidad y un manifiesto de procedencia en un directorio nuevo. No se modifica el snapshot original ni se rellenan datos ausentes. Un error de calidad impide publicar la tabla y señala la ruta del informe. Consulta [la arquitectura](docs/architecture.md) para el esquema y los controles.

La preparación real de las 7.033 sesiones de SPY pasó los controles implementados. Sigue pendiente verificar el calendario bursátil completo y contrastar precios con otra fuente. El comando completo se describe a continuación.

## Flujo completo desde la terminal

Desde la raíz del repositorio, activa el entorno y ejecuta:

```bash
source .venv/bin/activate
python -m tfm prepare-prices --config configs/data.toml
```

Este comando descarga un nuevo snapshot, prepara los precios y muestra las rutas del resultado y del registro. Para volver a preparar una descarga concreta sin acceder a Yahoo:

```bash
python -m tfm prepare-prices --config configs/data.toml --snapshot RUTA_DEL_SNAPSHOT
```

La descarga reutilizada debe tener los mismos parámetros de proveedor, instrumento, periodo y opciones de descarga que la configuración. Las rutas relativas de `--config` y `--snapshot` parten del directorio actual. Las rutas de almacenamiento dentro del TOML parten del padre de la carpeta que contiene la configuración: mantén los TOML en `configs/`. Así se resuelven los datos en el mismo lugar aunque ejecutes el comando desde otro directorio con una ruta absoluta al TOML.

Cada intento tiene su directorio `outputs/runs/<run_id>/`, excluido de Git:

- `run.json`: estado, fase, tiempos UTC, rutas, versiones y commit de Git, con indicación de cambios locales.
- `config.toml`: copia de la configuración y su huella registrada en `run.json`.
- En ejecuciones completadas: `source_manifest.json`, `prepared_manifest.json` y `quality_report.json`.

Si falla la descarga o la preparación, el comando devuelve código 1 e indica el registro. Un rechazo de calidad deja también la ruta del informe en `run.json`; los originales se conservan. Las ejecuciones interrumpidas con Ctrl+C se registran como `interrupted`. Una terminación forzada o un fallo del propio almacenamiento puede impedir actualizar el registro y dejarlo en `running`.

No se sobrescriben ejecuciones anteriores ni se elige automáticamente una descarga reciente: la repetición exige indicar el snapshot. El registro de Git identifica la revisión y si había cambios; para reconstruir exactamente el código usado, conserva esos cambios en un commit.

El comando se comprobó con el snapshot real de 7.033 sesiones, sin red y desde fuera del repositorio. No requiere dependencias adicionales a las ya instaladas.

## Menú interactivo

Desde la raíz del repositorio:

```bash
source .venv/bin/activate
python -m tfm
```

En una terminal aparece un menú para descargar y preparar, escoger una descarga existente por número, consultar ejecuciones, ver la configuración, cambiar configuración o salir. Las acciones utilizan directamente `configs/data.toml`; la opción 4 muestra su contenido sin preguntar. La opción 5 permite elegir otro TOML para esta sesión del menú; Intro o 0 cancela ese cambio. Se muestra el instrumento y el periodo antes de ejecutar. Al elegir una descarga, escribe uno de los números mostrados; 0 vuelve al menú. Al terminar se muestran sesiones, periodo, controles de calidad y rutas de resultados. Ctrl+C cancela la acción y Ctrl+D sale.

Los comandos con argumentos siguen disponibles. Sin argumentos y sin terminal interactiva se muestra ayuda, sin esperar respuestas. No se añaden dependencias para el menú.

El menú limpia la pantalla al cambiar de vista. Los resultados, errores y consultas permanecen visibles hasta pulsar Intro para volver. La limpieza solo se aplica en terminales compatibles; no se introducen códigos de control en salidas redirigidas.


## Simular comprar y mantener

Desde la raíz del repositorio, con el entorno virtual activado, ejecuta `python -m tfm` y elige **6. Simular comprar y mantener**. Selecciona por número una preparación compatible. El menú muestra primero intervalo y coste, y utiliza el mismo flujo que el comando:

```bash
python -m tfm simulate-buy-and-hold --config configs/buy_and_hold.toml --prepared RUTA_DE_PRECIOS_PREPARADOS
```

`RUTA_DE_PRECIOS_PREPARADOS` es un directorio bajo `data/processed/prices/` con Parquet, manifiesto e informe aprobados. Se elige explícitamente; no se descarga nada ni se toma automáticamente la preparación más reciente.

La configuración independiente `configs/buy_and_hold.toml` contiene inicio y fin **inclusivos**, coste en puntos básicos y las convenciones admitidas. Las fechas deben quedar dentro de la cobertura del archivo. La primera sesión del intervalo es la decisión: se compra al cierre de la segunda y la nueva posición recibe el retorno desde ese cierre. Se requieren al menos tres sesiones. Cambiar el intervalo reinicia la estrategia en efectivo; no arrastra posiciones anteriores. Cuando se comparen anomalías, sus fechas efectivas deberán alinearse con las del benchmark.

La opción 5 sigue cambiando solo la configuración de datos. La opción 6 utiliza `buy_and_hold.toml` del mismo directorio `configs/` y muestra su ruta; los parámetros financieros se editan allí. Las rutas de almacenamiento y política declaradas en TOML parten de la raíz del proyecto deducida de `configs/`. Las rutas de `--config` y `--prepared` parten del directorio de ejecución.

La política de desarrollo se lee de `[validation]` en `configs/experiment_base.toml`, mediante `validation.policy_config`; todavía no se interpreta su resto como un experimento ejecutable. Se rechazan intervalos y preparaciones completas que invadan el periodo final. No basta con recortar un archivo que incluya datos reservados. El protocolo de evaluación final se incorporará en otro incremento.

Convenciones: capital inicial 1, exposición 0/1 sin cortos, efectivo no remunerado, retornos de cierre ajustado como aproximación a rentabilidad total y sin liquidación final automática. No se suman dividendos otra vez. El coste inicial de 5 puntos básicos (0,05 %) es ilustrativo y configurable; no representa una tarifa de bróker verificada. Mantener exposición 1 no genera nuevas compras diarias.

Cada intento deja su registro en `outputs/runs/<run_id>`. Una ejecución completada guarda `config.toml`, `validation_policy.toml`, manifiesto e informe de los precios, `equity.parquet` y `summary.json`. El registro contiene huellas de configuraciones y resultados, versiones y estado de Git. La tabla distingue posiciones antes/después del cierre, retorno bruto/neto, rotación, coste monetario y capital bruto/neto. El resumen añade rentabilidades acumuladas, coste en unidades de capital, rotación y caída máxima neta como magnitud positiva. La caída incluye el capital inicial, por lo que recoge el coste de entrada. La suma de costes monetarios no equivale a la diferencia entre rentabilidades acumuladas.

Los errores e interrupciones se registran y no publican una trayectoria finalizada. No se sobrescriben precios ni ejecuciones anteriores. El historial del menú identifica descargas y simulaciones y muestra las rutas de sus resultados. El calendario se comprueba con una auditoría seleccionada explícitamente; sin ella se muestra pendiente. El contraste numérico con otra fuente sigue pendiente. No se han implementado Sharpe, DSR, PBO ni interpretación de modelos en este incremento.


## Auditar las sesiones del calendario

Ejecuta `python -m tfm` y elige **7. Auditar calendario de precios preparados**, o usa:

```bash
python -m tfm audit-prices --config configs/audit.toml --prepared RUTA_DE_PRECIOS_PREPARADOS
```

Se contrasta **todo el intervalo solicitado del manifiesto**, con final exclusivo, contra XNYS como referencia de sesiones diarias US. No se rellena ni modifica ningún precio. El informe separa calendario de precios, dividendos y ajustes: aprobar calendario no acredita esos otros campos. Funciona sin red después de instalar las dependencias.

Para usar el resultado en una simulación, selecciona la auditoría por número en la opción 6 o añade `--audit RUTA_DE_EJECUCION_DE_AUDITORIA` al comando `simulate-buy-and-hold`. No se elige automáticamente la última auditoría. Se comprueban huellas, cobertura, configuración/política y versión; se rechazan informes de otra preparación, parciales o con discrepancias. Se copia el informe empleado para conservar su procedencia. Sin auditoría sigue disponible el benchmark exploratorio, con calendario pendiente.

Consulta [el alcance, formato y limitaciones de la auditoría](docs/calendar_audit.md). Los informes y resultados anteriores permanecen intactos. Si aparecen discrepancias, se conserva la lista y la ejecución de auditoría puede quedar completada técnicamente con un resultado de calendario fallido; no se presenta como superada.

## Contraste con el emisor

La opción 8 del menú permite importar el Excel oficial de State Street y contrastar todas las distribuciones del desarrollo. La opción 7 sigue auditando solo calendario. Véase [source_reconciliation.md](docs/source_reconciliation.md) para los comandos, la política de comparación, los resultados reales y las limitaciones pendientes. No se modifican los originales ni se certifican cierres o ajustes a partir de dividendos.

## Preparar la historia mensual del estudio principal

```bash
python -m tfm prepare-shiller
```

La opción 9 del menú ofrece descarga, importación de un XLS local y reutilización de un original archivado. El resumen debe mostrar 768 meses: 12 de historia previa y 756 de desarrollo. Se conserva P como precio medio mensual y D como dividendo anualizado, sin tratarlos como cierres de ejecución o pagos mensuales. Véanse [los comandos, el contrato y las limitaciones](docs/shiller_monthly.md). La memoria ya recoge ese alcance; la simulación requiere cerrar las decisiones del [protocolo mensual](docs/monthly_protocol.md).


## Generar las señales mensuales de Shiller

En el menú `python -m tfm`, elige la **opción 10** y selecciona por número una preparación mensual existente. La opción 9 permite prepararla si todavía no tienes ninguna. No se elige automáticamente la última tabla ni se descargan datos al generar señales.

También puedes ejecutar:

```bash
python -m tfm build-shiller-signals --prepared RUTA_DE_PREPARACION_SHILLER
```

La configuración es `configs/shiller_signals.toml`: momentum 12–1 largo/efectivo y reversión de un mes largo/corto. La salida conserva mes de decisión, mes objetivo, indicadores y señales (+1 largo, -1 corto, 0 efectivo). Un campo vacío significa historia insuficiente. Con la preparación desde enero de 1926 hay 756 meses objetivo de 1927–1989 y 755 comparables para ambas reglas, desde febrero de 1927.

Cada ejecución guarda `signals.parquet`, `signals.csv` para consultar la tabla, `summary.json` y la procedencia. Se verifican integridad y política temporal antes de calcular. Son señales sobre promedios mensuales, sin dividendos, financiación, costes ni resultados de inversión. Véase [el contrato y las limitaciones](docs/monthly_protocol.md).
