# ¿Invertir o esperar?

Herramienta local del TFM de Ciencia de Datos para preparar datos y estudiar reglas de momentum y reversión. Prepara Shiller, SPY y RF de French por separado, calcula señales de Shiller y prepara los componentes de rentabilidad mensual. También simula comprar y mantener, momentum y reversión hasta 1989. Compara también la sensibilidad a costes y dividendos. Incluye un filtro sencillo de mercado bajista. También ajusta la exposición por volatilidad y reúne las alternativas sencillas. El entrenamiento de modelos y la evaluación desde 1990 siguen pendientes.

## Tercera entrega: diagnóstico de fuentes

Empieza por [00_diagnostico_fuentes.ipynb](notebooks/00_diagnostico_fuentes.ipynb). Este nuevo recorrido no utiliza CLI ni archivos de configuración. Revisa Shiller, los diarios de `^GSPC` de Yahoo, las doce carteras industriales de French y Baa/Aaa de FRED. Conserva las fuentes separadas, limita los importes analizados al desarrollo 1927–1989 y muestra la disponibilidad inicial de características con calentamiento y rezagos propuestos.

El diagnóstico compara la media de Shiller, el promedio de cierres diarios de Yahoo y su último cierre mensual disponible. Informa diferencias de señales, variabilidad, correlación entre meses y resultados teóricos brutos por precio. No incorpora dividendos o costes, no entrena y no certifica precios de ejecución o calendarios completos. Las diferencias entre proveedores se separan del contraste de promediar dentro de Yahoo.

Reutiliza `data/raw/shiller.xls` y guarda nuevos originales bajo `data/raw/diagnosis/`; los CSV son los originales de FRED, no copias de tablas preparadas. Las tablas del diagnóstico se guardan en `outputs/diagnosis/`, sin regenerar datos de trabajo ni simulaciones. La primera ejecución necesita red si faltan originales. No requiere dependencias nuevas.

Los hallazgos verificados, sus cifras y límites se recogen en [docs/diagnostico_fuentes.md](docs/diagnostico_fuentes.md).

La CLI y `configs/estudio.toml` que aparecen en los recorridos anteriores se mantienen temporalmente por compatibilidad. Se retirarán en el siguiente incremento; la entrega se organizará mediante notebooks con fuentes y supuestos explícitos.

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
8. Simular estrategias básicas
9. Comparar costes y dividendos
10. Comparar con filtro bajista
11. Comparar reglas, filtro bajista y volatilidad
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

Esto añade `ipykernel`, el motor de ejecución, y `matplotlib` para las curvas del tercer cuaderno; no instala la aplicación completa de JupyterLab. El editor debe tener soporte de notebooks. Ejecuta las celdas en orden y, para comprobar su reproducción, reinicia el kernel y ejecuta todo. La celda de preparación reutiliza el XLS de trabajo o lo descarga si falta; regenera las tablas de trabajo. Consulta [notebooks/README.md](notebooks/README.md) antes de ejecutarla. Los cuadernos se versionan sin salidas ni datos incrustados.

## Componentes de rentabilidad mensual

Después de preparar Shiller (opción 1), prepara RF de French (opción 6) y los componentes (opción 7). Consulta las tablas en la opción 3. También puedes ejecutar [02_componentes_de_rentabilidad.ipynb](notebooks/02_componentes_de_rentabilidad.ipynb), que reutiliza el Shiller preparado y muestra un mes desglosado.

La tabla contiene `price_return = P[t]/P[t-1]-1`, `dividend_return_approx = (D[t]/12)/P[t-1]`, su suma `total_return_approx` y `rf_return`. Las rentabilidades se guardan en **decimal mensual**: `0.002` significa `0,20 %`. RF ya es mensual: solo se divide por 100 al leer el porcentaje de French, nunca por doce. RF representa una alternativa de efectivo y no se suma a la rentabilidad del índice.

Solo se prepara 1927–1989. Las fechas deben coincidir exactamente: no se rellenan huecos ni se descartan meses para conseguir el cruce. El ZIP original completo de French puede contener fechas posteriores; solo se convierte RF del desarrollo. Los demás factores y la tabla anual no se utilizan. Los dividendos de Shiller siguen siendo anualizados e interpolados; D/12 se etiqueta como aproximación contable, no como un pago observado ni información acreditada en tiempo real.

Estos componentes todavía **no son resultados de estrategias**: no se aplican señales, posiciones, negociación, préstamo ni costes. Los supuestos y escenarios de préstamo acordados se conservan en `docs/decisiones.md` para las simulaciones y la memoria.

## Simular las estrategias básicas

Con Shiller, señales y componentes preparados, ejecuta la **opción 8** o abre [03_estrategias_basicas.ipynb](notebooks/03_estrategias_basicas.ipynb). El simulador no descarga datos ni utiliza importes desde 1990. Guarda las tres cuentas mensuales en `data/processed/baseline_simulations.parquet` y el resumen en su JSON.

La sección `[simulation]` fija capital inicial, coste por importe negociado, préstamo anual e inclusión del dividendo aproximado. Las tasas son decimales: `0.001` representa 0,10 % de negociación; `0.01`, 1 % anual de préstamo. Son escenarios hipotéticos, no tarifas históricas observadas. `include_dividends = false` permite la sensibilidad solo con precios, manteniendo las señales originales.

El objetivo mensual es invertir +100 %, 0 % o −100 % del capital después de comisiones. Se cobran el nominal realmente negociado para alcanzar ese objetivo y la liquidación final. Una posición corta puede necesitar reajuste aunque su señal no cambie. Los dividendos de los largos se reinvierten sin una comisión separada; los cortos deben el dividendo, pagan préstamo sobre el nominal inicial del mes y reciben RF solo por el capital aportado, sin interés adicional sobre los ingresos de la venta corta. No se simulan llamadas de margen intramensuales. Una cuenta que pierde todo su capital detiene la simulación en vez de continuar con capital negativo.

El cuaderno muestra el balance de un mes por estrategia, la curva de capital, drawdown y resumen. Sharpe usa exceso mensual sobre RF y se anualiza con raíz de 12; se deja sin valor si la dispersión es nula. La caída máxima incluye el capital inicial. Las rentabilidades son resultados del desarrollo bajo la aproximación de Shiller, no evidencia de mejora de un filtro ni una evaluación final.

Regenerar Shiller, French, las señales o los componentes retira las simulaciones anteriores. Cambiar los parámetros de simulación obliga a simular de nuevo antes de consultar el resultado, sin exigir volver a descargar o preparar las fuentes.

## Comprobar la sensibilidad a los supuestos

La **opción 9**, `python -m tfm analyze-sensitivity` o [04_sensibilidad.ipynb](notebooks/04_sensibilidad.ipynb) comparan los supuestos usando los mismos componentes, señales, fechas y simulador. No hace falta volver a descargar, editar la configuración entre ejecuciones ni ejecutar antes la opción 8.

Se conserva el central de `[simulation]` y se modifica **un supuesto cada vez**: negociación del 0 %, 0,10 %, 0,25 % y 0,50 %; préstamo anual del 0,25 %, 1 % y 3 %; y la inclusión/exclusión de dividendos aproximados. Los otros valores permanecen como en el central. Con la configuración inicial son **siete escenarios × tres estrategias = 21 resúmenes**; el central no se repite. Si configuras una tarifa central distinta de las previstas, se conserva además de esas alternativas y aumenta el número de escenarios. Las listas prefijadas están en `src/tfm/sensitivity.py`.

Se guardan `baseline_sensitivity.parquet` y su JSON, conservando `baseline_simulations` y todas las fuentes. La tabla incluye cada supuesto, métricas y diferencia de rentabilidad anualizada frente al central. Las tasas se guardan en decimal; para mostrar la diferencia en puntos porcentuales se multiplica por 100. No se guardan cuentas mensuales adicionales. Una cuenta insolvente detiene la comparación completa y conserva la salida anterior; no se omite el escenario problemático.

El préstamo no afecta a comprar y mantener ni al momentum actual, porque no venden en corto. Excluir dividendos elimina ingresos de los largos y pagos de los cortos; no es una comisión adicional. La comparación no estudia todas las combinaciones de costes, no elige el escenario más rentable ni demuestra robustez fuera de muestra. Las limitaciones de precios medios y dividendos reconstruidos siguen vigentes. Cambiar la configuración o regenerar entradas obliga a repetir la comparación.

## Comparar con un filtro de mercado bajista

La **opción 10**, `python -m tfm simulate-bear-filter` o [05_filtro_bajista.ipynb](notebooks/05_filtro_bajista.ipynb) comparan comprar y mantener, momentum y reversión, y las dos reglas con un filtro. Si `P[m]/P[m-24]-1 < 0`, el filtro deja la señal del mes siguiente en efectivo; con resultado cero o positivo, la acepta. No cambia el sentido de la señal, no mira el rebote futuro y no utiliza dividendos como predictor.

Es una **adaptación del indicador bajista de 24 meses de Daniel y Moskowitz (2016)** a la serie de precios medios de Shiller. El veto y su aplicación a ambas reglas son convenciones explícitas del TFM; no replican la cartera transversal ni la estrategia dinámica del artículo. No se añade un umbral de volatilidad ni se optimiza la ventana. El ajuste por volatilidad se compara por separado en la opción 11.

**Tras actualizar este incremento, repite los notebooks 01 y 02 antes de abrir el 05.** La configuración amplía la historia a diciembre de 1924 para calcular el indicador de enero de 1927 sin perder meses del desarrollo. Son 781 observaciones preparadas: 25 de historia previa y los mismos 756 meses de 1927–1989. No necesitas un nuevo proveedor ni otra descarga si conservas los originales completos. Desde el menú puedes usar **1 → 2 → 6 → 7 → 10** (la opción 6 puede omitirse si RF ya está preparado).

La comparación guarda las cinco cuentas mensuales con sus señales e indicador en `bear_filter_simulations.parquet` y un resumen JSON. Mantiene las cuentas y sensibilidades anteriores mientras sean compatibles con la configuración actual. Si faltan meses de historia, se detiene sin rellenarlos ni acortar la comparación. Al regenerar entradas se retira esta salida; cambiar costes requiere volver a simularla. No se han evaluado meses desde 1990.

## Ajustar exposición por volatilidad y reunir comparadores

La **opción 11**, `python -m tfm compare-simple-strategies` o [06_ajuste_volatilidad.ipynb](notebooks/06_ajuste_volatilidad.ipynb) comparan ocho cuentas en los mismos 756 meses: las tres básicas, las dos con veto bajista y las tres básicas ajustadas por volatilidad. Comprar y mantener ajustado sirve de control para distinguir el efecto de gestionar exposición del efecto de las señales. El veto bajista y el escalado se aplican como alternativas separadas.

En `[volatility_scaling]` se declaran **12 variaciones mensuales anteriores**, objetivo anual **12 %** y exposición máxima **1**. Al decidir en m, se calcula la desviación típica muestral de las variaciones de precio hasta m, anualizada por raíz de 12. La escala es `min(max_exposure, target_annual_volatility / estimated_annual_volatility)` y se aplica a la señal de m+1. Si la estimación es exactamente cero, se usa la exposición máxima. Faltar historia detiene el cálculo; no equivale a riesgo cero. No se estima una constante con toda la muestra ni se buscan parámetros por rentabilidad.

La adaptación usa riesgo mensual del índice e inversa de desviación típica. No replica el riesgo diario de la cartera transversal de Barroso y Santa-Clara ni la regla principal de inversa de varianza de Moreira y Muir. El objetivo es una referencia, no una garantía de volatilidad realizada, especialmente con promedios de Shiller, exposición limitada y señales en efectivo.

El simulador admite posiciones parciales entre −1 y +1. Un largo del 40 % recibe precio y dividendos por ese 40 % y RF por el 60 % restante. Un corto del 40 % paga préstamo y dividendos sobre ese nominal y recibe RF solo por el capital aportado, sin remunerar adicionalmente el ingreso de la venta corta. Se cobran los reajustes de tamaño y la liquidación final; no hay apalancamiento. Las cuentas básicas conservan sus fórmulas y resultados.

Se escriben `simple_comparisons.parquet` y su JSON con las ocho cuentas, riesgo estimado y escala aplicada. Se conservan los otros resultados. Cambiar `[volatility_scaling]` solo exige repetir esta comparación, sin preparar ni descargar fuentes. Regenerar entradas la invalida. Si ya has ejecutado los notebooks 01 y 02 con historia desde diciembre de 1924, abre directamente el 06; no hay otra ampliación histórica ni nuevas dependencias. No se evalúan fechas desde 1990.

## Datos y configuración

Solo hay una configuración: [configs/estudio.toml](configs/estudio.toml). Contiene las fuentes de Shiller y French, los periodos del estudio, las convenciones de las reglas y el periodo diario solicitado para SPY. La opción 5 explica sus valores. El menú vuelve a leer el archivo antes de cada tarea.

La sección `[spy]` solo admite `start` y `end`. El activo está fijado en SPY; otros parámetros se rechazan antes de descargar.

- **Shiller:** historia previa desde diciembre de 1924, desarrollo 1927–1989 y evaluación desde 1990 deshabilitada. Es la serie principal del estudio. P es un precio medio mensual y D es anualizado e interpolado. Las variaciones entre promedios se estudiarán como aproximación histórica, no como operaciones ejecutadas a esos precios. Los supuestos centrales de simulación se documentan en la sección anterior y en `docs/decisiones.md`.
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
data/processed/baseline_simulations.parquet        Cuenta mensual de las tres estrategias
data/processed/baseline_sensitivity.parquet        Resúmenes comparados de costes y dividendos
data/processed/bear_filter_simulations.parquet    Cinco cuentas, indicador bajista y señales originales
data/processed/simple_comparisons.parquet         Ocho cuentas con comparadores de riesgo y régimen
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
  returns.py              Componentes de rentabilidad
  simulation.py           Cuenta y resumen de las tres estrategias básicas
  sensitivity.py          Escenarios prefijados con el mismo simulador
  comparators.py          Veto bajista de 24 meses y comparación con las reglas originales
  volatility.py           Riesgo previo, escala sin apalancamiento y comparación conjunta
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
python -m tfm simulate-baselines
python -m tfm analyze-sensitivity
python -m tfm simulate-bear-filter
python -m tfm compare-simple-strategies
python -m tfm status
```

`prepare-returns` requiere Shiller y RF ya preparados; no descarga ni necesita las señales. `prepare-data --source french --file "/ruta/al/F-F_Research_Data_Factors_CSV.zip"` permite importar el ZIP oficial sin red. `prepare-data` reutiliza el original de trabajo o descarga si falta. Para empezar sin red, añade `--file "/ruta/al/original.xls"`; con `--source spy`, indica el Parquet original de Yahoo, con sus columnas originales y su JSON de procedencia junto a él: `spy_fuente.json` para `spy.parquet`, o `manifest.json` para los originales de la etapa anterior. Si el archivo se ha renombrado, su procedencia se busca como `<nombre>_fuente.json`. Un archivo normalizado no sirve como original de Yahoo.

Los comandos admiten `--config` para indicar un archivo de estudio dentro de `configs/`; las salidas parten de su raíz de proyecto. Sin `--config`, se localiza la configuración desde el paquete. Sin argumentos y sin terminal interactiva, se muestra ayuda y no se esperan respuestas.

Los comandos antiguos `prepare-prices`, `prepare-shiller`, `build-shiller-signals`, `simulate-buy-and-hold`, `audit-prices` e `import-ssga-dividends` se han retirado. La preparación actual utiliza `prepare-data`; el cálculo de señales, `calculate-signals`. La simulación mensual actual utiliza `simulate-baselines`, con los supuestos de Shiller; no recupera la lógica del simulador diario retirado.

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
