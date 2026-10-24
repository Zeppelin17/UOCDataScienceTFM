# ¿Invertir o esperar?

Herramienta local del TFM de Ciencia de Datos para preparar datos y estudiar reglas de momentum y reversión. Prepara Shiller, SPY y RF de French por separado, calcula señales de Shiller y prepara los componentes de rentabilidad mensual. La simulación de estrategias y el entrenamiento de modelos siguen pendientes.

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
6. Preparar RF de French (rentabilidad del efectivo)
7. Preparar componentes de rentabilidad mensual
0. Salir
```

Para continuar con los datos que ya tienes, elige **1 → Reutilizar un original de la etapa anterior**, selecciona su número y espera el resumen. Después utiliza **2** para calcular las señales y **3** para consultar resultados y las primeras cinco filas. Los originales anteriores no se modifican.

Cada tarea identifica la fuente, el periodo, la entrada, el resultado y el siguiente paso. Si falta un original, permite descargar, importar un archivo propio o escoger uno anterior por fecha y número. No elige automáticamente la última copia. Si ya existe el original de trabajo, lo reutiliza sin descargar.

**0** vuelve o sale. **Intro** cierra un resultado. **Ctrl+C** cancela la tarea y **Ctrl+D** cierra el menú. La pantalla se limpia en terminales compatibles y mantiene el resultado hasta Intro. No hay apertura de archivos mediante Finder ni otros gestores del sistema.

## Comprender el estudio con un notebook

Abre [01_datos_y_senales.ipynb](notebooks/01_datos_y_senales.ipynb) para preparar Shiller y entender las señales paso a paso. El cuaderno usa las mismas funciones y configuración que la CLI; no es necesario ejecutar antes el menú. Todavía no calcula rentabilidades de estrategias ni entrena modelos.

En un editor compatible con Jupyter, selecciona el intérprete de `.venv` como kernel. El soporte de Python para cuadernos es opcional:

```bash
python -m pip install -e ".[notebooks]"
```

Esto añade `ipykernel`, el motor de ejecución; no instala la aplicación completa de JupyterLab. El editor debe tener soporte de notebooks. Ejecuta las celdas en orden y, para comprobar su reproducción, reinicia el kernel y ejecuta todo. La celda de preparación reutiliza el XLS de trabajo o lo descarga si falta; regenera las tablas de trabajo. Consulta [notebooks/README.md](notebooks/README.md) antes de ejecutarla. Los cuadernos se versionan sin salidas ni datos incrustados.

## Componentes de rentabilidad mensual

Después de preparar Shiller (opción 1), prepara RF de French (opción 6) y los componentes (opción 7). Consulta las tablas en la opción 3. También puedes ejecutar [02_componentes_de_rentabilidad.ipynb](notebooks/02_componentes_de_rentabilidad.ipynb), que reutiliza el Shiller preparado y muestra un mes desglosado.

La tabla contiene `price_return = P[t]/P[t-1]-1`, `dividend_return_approx = (D[t]/12)/P[t-1]`, su suma `total_return_approx` y `rf_return`. Las rentabilidades se guardan en **decimal mensual**: `0.002` significa `0,20 %`. RF ya es mensual: solo se divide por 100 al leer el porcentaje de French, nunca por doce. RF representa una alternativa de efectivo y no se suma a la rentabilidad del índice.

Solo se prepara 1927–1989. Las fechas deben coincidir exactamente: no se rellenan huecos ni se descartan meses para conseguir el cruce. El ZIP original completo de French puede contener fechas posteriores; solo se convierte RF del desarrollo. Los demás factores y la tabla anual no se utilizan. Los dividendos de Shiller siguen siendo anualizados e interpolados; D/12 se etiqueta como aproximación contable, no como un pago observado ni información acreditada en tiempo real.

Estos componentes todavía **no son resultados de estrategias**: no se aplican señales, posiciones, negociación, préstamo ni costes. Los supuestos y escenarios de préstamo acordados se conservan en `docs/decisiones.md` para el siguiente bloque y la memoria.

## Datos y configuración

Solo hay una configuración: [configs/estudio.toml](configs/estudio.toml). Contiene las fuentes de Shiller y French, los periodos del estudio, las convenciones de las reglas y el periodo diario solicitado para SPY. La opción 5 explica sus valores. El menú vuelve a leer el archivo antes de cada tarea.

La sección `[spy]` solo admite `start` y `end`. El activo está fijado en SPY; otros parámetros se rechazan antes de descargar.

- **Shiller:** historia previa desde diciembre de 1925, desarrollo 1927–1989 y evaluación desde 1990 deshabilitada. Es la serie principal del estudio. P es un precio medio mensual y D es anualizado e interpolado. Las variaciones entre promedios se estudiarán como aproximación histórica, no como operaciones ejecutadas a esos precios. Los supuestos concretos de simulación siguen pendientes.
- **French:** solo RF del ZIP mensual de tres factores, de 1927 a 1989. Se usa para el efectivo; no sustituye al índice por la cartera de mercado de French.
- **SPY:** datos diarios del ETF mediante Yahoo Finance y `yfinance`, inicialmente desde 1993 hasta 2020. Se mantienen separados de Shiller y su utilización definitiva sigue pendiente.

Las salidas tienen nombres fijos:

```text
data/raw/shiller.xls                    Original de trabajo de Shiller
data/raw/shiller_fuente.json            Procedencia de ese original
data/raw/french_factors.zip             Original ZIP mensual de French
data/raw/french_factors_fuente.json      Procedencia del ZIP
data/raw/spy.parquet                    Original de trabajo de Yahoo
data/raw/spy_fuente.json                Procedencia de ese original
data/processed/shiller_monthly.parquet   Observaciones mensuales preparadas
data/processed/shiller_signals.parquet   Señales de momentum y reversión
data/processed/spy_prices.parquet        Precios diarios normalizados
data/processed/french_rf_monthly.parquet RF mensual en decimal
data/processed/monthly_return_components.parquet  Precio, dividendo aproximado y RF
```

Cada tabla preparada tiene un resumen `.json`. Las tablas derivadas se regeneran en sus rutas habituales; preparar Shiller retira las señales y los componentes anteriores cuando termina correctamente; preparar French retira los componentes, conservando las señales. Durante la sustitución se conserva en memoria el contenido anterior para restaurar tabla, resumen y señales si ocurre un error. No se crean archivos permanentes de respaldo. Cambiar la configuración temporal obliga a preparar de nuevo antes de calcular señales.

Los originales de trabajo no se sustituyen automáticamente. Si necesitas actualizar uno, conserva primero una copia con su JSON de procedencia y retira el original de su ruta de trabajo antes de importar o descargar otro; después regenera los datos preparados y sus señales. Los originales y resultados históricos permanecen en sus carpetas y quedan fuera de Git, igual que los datos nuevos.

Antes de reutilizar o importar SPY se comprueba que su JSON declara Yahoo, SPY y el mismo periodo solicitado. Si cambias las fechas, se pide un original de ese periodo; no se vuelve a etiquetar la descarga antigua con las fechas nuevas. Esto comprueba el periodo declarado de adquisición y no certifica todas las sesiones del calendario.

Las comprobaciones detectan problemas de estructura, cobertura mensual, fechas, valores y coherencia de precios. No certifican la exactitud financiera de una fuente. La herramienta no crea CSV, identificadores de ejecución, huellas de integridad, copias de configuraciones ni registros del estado de Git.

Las [decisiones y limitaciones](docs/decisiones.md) explican las reglas, las cuestiones metodológicas abiertas y los hallazgos previos que deben conservarse para el TFM.

## Arquitectura

```text
Menú, comando o notebook → configuración → lectura/descarga → preparación → señales o componentes
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
  returns.py              Componentes de rentabilidad; todavía sin estrategias
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
python -m tfm prepare-data --source french
python -m tfm prepare-returns
python -m tfm status
```

`prepare-returns` requiere Shiller y RF ya preparados; no descarga ni necesita las señales. `prepare-data --source french --file "/ruta/al/F-F_Research_Data_Factors_CSV.zip"` permite importar el ZIP oficial sin red. `prepare-data` reutiliza el original de trabajo o descarga si falta. Para empezar sin red, añade `--file "/ruta/al/original.xls"`; con `--source spy`, indica el Parquet original de Yahoo, con sus columnas originales y su JSON de procedencia junto a él: `spy_fuente.json` para `spy.parquet`, o `manifest.json` para los originales de la etapa anterior. Si el archivo se ha renombrado, su procedencia se busca como `<nombre>_fuente.json`. Un archivo normalizado no sirve como original de Yahoo.

Los comandos admiten `--config` para indicar un archivo de estudio dentro de `configs/`; las salidas parten de su raíz de proyecto. Sin `--config`, se localiza la configuración desde el paquete. Sin argumentos y sin terminal interactiva, se muestra ayuda y no se esperan respuestas.

Los comandos antiguos `prepare-prices`, `prepare-shiller`, `build-shiller-signals`, `simulate-buy-and-hold`, `audit-prices` e `import-ssga-dividends` se han retirado. La preparación actual utiliza `prepare-data`; el cálculo de señales, `calculate-signals`. No se incluye todavía un simulador en el flujo actual.

## Entorno y pruebas

Para crear un entorno nuevo, con Python 3.11 o posterior:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

En PowerShell, el comando de activación es `.venv\Scripts\Activate.ps1`. El entorno verificado es Python 3.14 en macOS; el archivo `requirements-lock.txt` recoge sus versiones. Para reproducir esas versiones, instala primero `python -m pip install -r requirements-lock.txt` y después `python -m pip install --no-deps -e .`. Este archivo fija el flujo base y pytest; el soporte opcional de notebooks se instala por separado con `python -m pip install -e ".[notebooks]"`. En otra versión de Python o plataforma, utiliza las dependencias de `pyproject.toml` y comprueba el entorno.

Se mantienen pandas, PyArrow, yfinance, xlrd y certifi. Se han retirado las dependencias de auditoría de calendario y del Excel SSGA. Esta limpieza no instala ni desinstala paquetes del entorno existente.

```bash
python -m pytest -q
```

Las pruebas cubren los lectores, la separación temporal, las reglas calculables a mano, la preparación, los errores principales y los recorridos del menú. No descargan datos ni alteran archivos del usuario. Véase [tests/README.md](tests/README.md).
