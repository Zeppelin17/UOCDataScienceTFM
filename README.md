# ¿Invertir o esperar?

Proyecto de programación del TFM de Ciencia de Datos: evaluación de filtros de aprendizaje automático para reglas de momentum y reversión sobre el S&P 500.

## Estado del proyecto

Entorno inicial preparado. Todavía no descarga datos, entrena modelos ni simula operaciones.

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

Se prevé utilizar pandas para el procesamiento y Parquet para persistir tablas. Las dependencias se añadirán cuando se implementen las funciones que las necesiten. DuckDB podrá incorporarse si las consultas SQL lo justifican.

- Conservar originales y registrar fuente, fecha de descarga y ajustes.
- Distinguir fecha observada, fecha disponible, decisión y ejecución.
- Mantener etiquetas futuras separadas de las variables explicativas.
- Identificar el activo incluso cuando solo se estudie SPY.
- Registrar configuraciones, versiones, semillas y particiones por ejecución.
- No sobrescribir resultados de experimentos anteriores.

El bloque de desarrollo termina en 2020. El periodo desde 2021 hasta el corte disponible de 2026 se reserva para la evaluación final. No debe utilizarse para seleccionar variables, modelos o filtros. La configuración inicial deja la fecha final pendiente de concretar.

## Entorno local

Se propone Python 3.11 o posterior. Para crear un entorno aislado:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

La instalación editable utiliza setuptools como herramienta de construcción. pandas procesa las tablas, PyArrow permite persistir Parquet y el extra `dev` incorpora pytest. El proveedor de descarga se añadirá tras verificar la fuente. Para comprobar que el paquete se importa tras instalarlo:

```bash
python -c "import tfm; print(tfm.__version__)"
```

## Desarrollo incremental

1. Primera fuente y reconstrucción de tablas desde originales.
2. Simulador básico con comprar y mantener y costes.
3. Momentum y reversión con ejemplos verificables.
4. Variables de entorno, integración de fuentes y filtros sencillos.
5. Etiquetas, particiones temporales y registro de configuraciones.
6. Primer meta-modelo sencillo y predicciones fuera de muestra.
7. Alternativas justificadas, SHAP y controles DSR/PBO.
8. Configuración fijada, evaluación final y exportación de resultados.

Consulta `docs/architecture.md` para los contratos y las decisiones pendientes.

## Verificación

Los tests se añadirán con cada comportamiento implementado. Priorizarán disponibilidad temporal de datos, ventanas de señales, separación de etiquetas, ejecución y costes, purga de particiones cuando corresponda y un recorrido completo con datos pequeños calculables a mano.

El framework de tests es pytest. Se ejecuta con `python -m pytest`; los tests de procesamiento se añadirán al implementar cada incremento. Los módulos actuales son únicamente marcadores de responsabilidades.

### Dependencias reproducibles

`requirements-lock.txt` registra las versiones verificadas con Python 3.14 en macOS. Para reproducir ese entorno, instala primero `python -m pip install -r requirements-lock.txt` y después `python -m pip install --no-deps -e .`. En otra versión de Python o plataforma, resuelve las dependencias de `pyproject.toml` y valida antes de renovar este archivo.

## Fuente de precios propuesta

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

La preparación real de las 7.033 sesiones de SPY pasó los controles implementados. Sigue pendiente verificar el calendario bursátil completo y contrastar precios con otra fuente. El comando que unirá descarga y preparación se añadirá en el siguiente incremento.
