# ¿Invertir o esperar?

Herramienta local del TFM de Ciencia de Datos para preparar datos y estudiar reglas de momentum y reversión. Actualmente prepara Shiller y SPY por separado y calcula señales de Shiller. La simulación de rentabilidades y el entrenamiento de modelos siguen pendientes.

## Empezar

Con el entorno virtual existente activado, desde la raíz del repositorio:

```bash
python -m tfm
```

```text
1. Preparar datos de Shiller
2. Calcular señales de momentum y reversión
3. Consultar datos y señales preparados
4. Trabajar con datos de SPY de Yahoo Finance
5. Ver la configuración del estudio
0. Salir
```

Para continuar con los datos que ya tienes, elige **1 → Reutilizar un original de la etapa anterior**, selecciona su número y espera el resumen. Después utiliza **2** para calcular las señales y **3** para consultar resultados y las primeras cinco filas. Los originales anteriores no se modifican.

Cada tarea identifica la fuente, el periodo, la entrada, el resultado y el siguiente paso. Si falta un original, permite descargar, importar un archivo propio o escoger uno anterior por fecha y número. No elige automáticamente la última copia. Si ya existe el original de trabajo, lo reutiliza sin descargar.

**0** vuelve o sale. **Intro** cierra un resultado. **Ctrl+C** cancela la tarea y **Ctrl+D** cierra el menú. La pantalla se limpia en terminales compatibles y mantiene el resultado hasta Intro. No hay apertura de archivos mediante Finder ni otros gestores del sistema.

## Datos y configuración

Solo hay una configuración: [configs/estudio.toml](configs/estudio.toml). Contiene la fuente de Shiller, los periodos del estudio, las convenciones de las reglas y el periodo diario solicitado para SPY. La opción 5 explica sus valores. El menú vuelve a leer el archivo antes de cada tarea.

- **Shiller:** historia previa desde 1926, desarrollo 1927–1989 y evaluación desde 1990 deshabilitada. P es un precio medio mensual y D es anualizado e interpolado. Todavía está pendiente acordar con el tutor cómo evaluar rentabilidades con esa información.
- **SPY:** datos diarios del ETF mediante Yahoo Finance y `yfinance`, inicialmente desde 1993 hasta 2020. Se mantienen separados de Shiller y su utilización definitiva sigue pendiente.

Las salidas tienen nombres fijos:

```text
data/raw/shiller.xls                    Original de trabajo de Shiller
data/raw/shiller_fuente.json            Procedencia de ese original
data/raw/spy.parquet                    Original de trabajo de Yahoo
data/raw/spy_fuente.json                Procedencia de ese original
data/processed/shiller_monthly.parquet   Observaciones mensuales preparadas
data/processed/shiller_signals.parquet   Señales de momentum y reversión
data/processed/spy_prices.parquet        Precios diarios normalizados
```

Cada tabla preparada tiene un resumen `.json`. Las tablas derivadas se regeneran en sus rutas habituales; preparar Shiller retira las señales anteriores cuando termina correctamente. Los fallos de calidad o de escritura de los archivos provisionales conservan las salidas válidas anteriores. Cambiar la configuración temporal obliga a preparar de nuevo antes de calcular señales.

Los originales de trabajo no se sustituyen automáticamente. Si necesitas actualizar uno, conserva primero una copia y retíralo de su ruta de trabajo antes de importar o descargar otro; después regenera los datos preparados y sus señales. Los originales y resultados históricos permanecen en sus carpetas y quedan fuera de Git, igual que los datos nuevos.

Las comprobaciones detectan problemas de estructura, cobertura mensual, fechas, valores y coherencia de precios. No certifican la exactitud financiera de una fuente. La herramienta no crea CSV, identificadores de ejecución, huellas de integridad, copias de configuraciones ni registros del estado de Git.

Las [decisiones y limitaciones](docs/decisiones.md) explican las reglas, las cuestiones metodológicas abiertas y los hallazgos previos que deben conservarse para el TFM.

## Arquitectura

```text
Menú o comando → configuración → lectura/descarga → preparación → señales
```

```text
configs/estudio.toml       Parámetros del estudio
src/tfm/
  __main__.py             Entrada de python -m tfm
  cli.py                  Comandos directos
  menu.py                 Recorridos guiados y consulta en terminal
  config.py               Lectura de configuración y comprobaciones
  data.py                 Coordinación y guardado con rutas fijas
  sources/                Lectura o descarga de Shiller y Yahoo
  preparation/            Normalización y calidad de cada fuente
  signals/                Fórmulas de momentum y reversión
notebooks/                Exploración y explicaciones, cuando sean necesarias
tests/                    Pruebas esenciales sin red
docs/decisiones.md        Supuestos, limitaciones y antecedentes
```

No requiere servidor, base de datos ni un gestor de experimentos. Los módulos de variables, etiquetas, modelos y evaluación se añadirán cuando los desarrollemos. La lógica reutilizable pertenece a `src/tfm`; los cuadernos pueden utilizarla para explorar y explicar resultados.

## Comandos directos

El menú llama a las mismas funciones que estos comandos:

```bash
python -m tfm prepare-data
python -m tfm calculate-signals
python -m tfm prepare-data --source spy
python -m tfm status
```

`prepare-data` reutiliza el original de trabajo o descarga si falta. Para empezar sin red, añade `--file "/ruta/al/original.xls"`; con `--source spy`, indica el Parquet original de Yahoo, con sus columnas originales. Un archivo normalizado no sirve como original de Yahoo.

Los comandos admiten `--config` para indicar un archivo de estudio dentro de `configs/`; las salidas parten de su raíz de proyecto. Sin `--config`, se localiza la configuración desde el paquete. Sin argumentos y sin terminal interactiva, se muestra ayuda y no se esperan respuestas.

Los comandos antiguos `prepare-prices`, `prepare-shiller`, `build-shiller-signals`, `simulate-buy-and-hold`, `audit-prices` e `import-ssga-dividends` se han retirado. La preparación actual utiliza `prepare-data`; el cálculo de señales, `calculate-signals`. No se incluye todavía un simulador en el flujo actual.

## Entorno y pruebas

Para crear un entorno nuevo, con Python 3.11 o posterior:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

En PowerShell, el comando de activación es `.venv\Scripts\Activate.ps1`. El entorno verificado es Python 3.14 en macOS; el archivo `requirements-lock.txt` recoge sus versiones. Para reproducir esas versiones, instala primero `python -m pip install -r requirements-lock.txt` y después `python -m pip install --no-deps -e .`. En otra versión de Python o plataforma, utiliza las dependencias de `pyproject.toml` y comprueba el entorno.

Se mantienen pandas, PyArrow, yfinance, xlrd y certifi. Se han retirado las dependencias de auditoría de calendario y del Excel SSGA. Esta limpieza no instala ni desinstala paquetes del entorno existente.

```bash
python -m pytest -q
```

Las pruebas cubren los lectores, la separación temporal, las reglas calculables a mano, la preparación, los errores principales y los recorridos del menú. No descargan datos ni alteran archivos del usuario. Véase [tests/README.md](tests/README.md).
