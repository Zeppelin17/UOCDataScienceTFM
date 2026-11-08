# UOC Data Science TFM

Estudio de aprendizaje automático como filtro de las señales de momentum y reversión. El desarrollo utiliza datos mensuales de **1927–1989**; la evaluación desde 1990 sigue pendiente y deshabilitada.

El trabajo se ejecuta mediante **notebooks**, sin CLI ni archivos de configuración. Los cuadernos muestran las fuentes, los periodos y los supuestos; las funciones reutilizables están en `src/tfm`.

## Cómo empezar

Con Python 3.11 o posterior, desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,notebooks]"
```

En PowerShell, activa el entorno con `.venv\Scripts\Activate.ps1`. Si ya tienes el entorno con ipykernel y matplotlib, este cambio no necesita instalar nada. `requirements-lock.txt` conserva las versiones verificadas del flujo base y pytest; las dependencias opcionales de notebooks se instalan por separado.

Abre los cuadernos con un editor compatible con Jupyter, selecciona el Python de `.venv`, reinicia el kernel y ejecuta las celdas en orden. Pueden ejecutarse desde la raíz del proyecto o desde `notebooks/`.

| Cuaderno | Qué hace | Entradas necesarias |
|---|---|---|
| [00 Diagnóstico](notebooks/00_diagnostico_fuentes.ipynb) | Contrasta medias y cierres y revisa fuentes de variables | Descarga originales si faltan; es independiente de 01–10 |
| [01 Datos y señales](notebooks/01_datos_y_senales.ipynb) | Prepara Shiller y calcula momentum y reversión | Descarga Shiller si falta, o permite indicar un XLS local |
| [02 Componentes](notebooks/02_componentes_de_rentabilidad.ipynb) | Prepara RF de French, variaciones de precio y dividendo aproximado | Haber ejecutado 01; descarga French si falta |
| [03 Estrategias básicas](notebooks/03_estrategias_basicas.ipynb) | Simula comprar y mantener y las dos reglas | Tablas de 01 y 02 |
| [04 Sensibilidad](notebooks/04_sensibilidad.ipynb) | Compara costes y dividendos, un supuesto cada vez | Tablas de 01 y 02 |
| [05 Filtro bajista](notebooks/05_filtro_bajista.ipynb) | Compara las reglas con un veto basado en los últimos 24 meses | Tablas de 01 y 02 |
| [06 Volatilidad](notebooks/06_ajuste_volatilidad.ipynb) | Compara ocho cuentas, incluyendo exposición ajustada por riesgo | Tablas de 01 y 02 |
| [07 Características](notebooks/07_caracteristicas.ipynb) | Construye diez variables de precio, riesgo, crédito e industrias | Shiller preparado con 01; reutiliza o descarga industrias y crédito |
| [08 Etiquetas](notebooks/08_etiquetas.ipynb) | Compara cada operación mensual con el efectivo y calcula una sensibilidad de negociación | Tablas de 01, 02 y 07 |
| [09 Cribado](notebooks/09_cribado_regimen.ipynb) | Relaciona el retorno de cada regla con las diez variables; revisa Holm, terciles, subperiodos y sombras | Haber ejecutado 01 → 02 → 07 → 08 |
| [10 Validación temporal](notebooks/10_validacion_temporal.ipynb) | Prepara quince particiones CPCV con purga y embargo y cuenta ejemplos por regla | Haber ejecutado 01 → 02 → 07 → 08; independiente del 09 |

El 00 puede ejecutarse por separado. Para reproducir las simulaciones, ejecuta 01 → 02 → 03–06. Los cuadernos 03–06 no necesitan ejecutarse entre sí. El 07 prepara diez características candidatas y no necesita las simulaciones ni el 02. Conserva 756 meses, de los que 749 tienen las diez variables completas. El 08 genera etiquetas centrales y una sensibilidad sin negociación, conservando las mismas filas. No se han entrenado modelos ni seleccionado variables por sus resultados. El 09 implementa el cribado descrito en [Hipótesis y protocolo](docs/hipotesis_y_cribado.md), con preparación causal y una muestra común tras su calentamiento. Es descriptivo: no selecciona automáticamente variables ni estima habilidad fuera de muestra.

El 10 implementa el [diseño de validación temporal](docs/plan_validacion_temporal.md): seis bloques, quince combinaciones, purga de un mes y embargo de seis meses. Separa el calendario de los ejemplos utilizables por regla, conserva las diez candidatas y no entrena modelos. Guarda las particiones y sus recuentos, sin depender de los resultados del cribado.

## Supuestos y datos

La fuente principal es Shiller: **promedios mensuales nominales**, no cierres negociables ni precios de SPY. Se conservan 25 meses previos de calentamiento desde diciembre de 1924 y 756 meses de desarrollo. D es anualizado e interpolado: dividirlo entre doce es una aproximación contable retrospectiva, no un pago observado ni un predictor conocido entonces.

El escenario central utiliza capital normalizado 100, negociación del 0,10 % del nominal, préstamo del 1 % anual para cortos y dividendos aproximados incluidos. Estos supuestos están visibles en los cuadernos 03–06. Si cambias uno, debes volver a ejecutar el cuaderno correspondiente; no se propaga automáticamente a los demás. El objetivo de volatilidad del 12 % y la ventana de 12 meses se muestran en el 06.

Las fuentes oficiales están fijadas en los lectores. `yfinance` sigue utilizándose en el diagnóstico de `^GSPC`. Las series no se empalman. Las [características](docs/caracteristicas.md) documentan fórmulas, unidades y retrasos. Consulta el [diagnóstico de fuentes](docs/diagnostico_fuentes.md) y las [decisiones y limitaciones](docs/decisiones.md).

## Archivos y arquitectura

```text
notebooks → fuentes y preparación → señales y componentes → simuladores → tablas y gráficos
```

```text
notebooks/                Recorrido explicativo y ejecución del estudio
src/tfm/
  data.py                 Preparación, lectura y guardado con nombres fijos
  sources/                Lectores y descargas
  preparation/            Normalización y controles de las fuentes
  signals/                Fórmulas de momentum y reversión
  returns.py              Precio, dividendo aproximado y RF
  simulation.py           Cuenta mensual y métricas
  sensitivity.py          Escenarios de costes y dividendos
  comparators.py          Filtro bajista
  volatility.py           Escalado por riesgo y comparación conjunta
  diagnostics.py          Cobertura de fuentes y contraste de medias/cierres
  features.py             Diez características con fechas de fuente explícitas
  labels.py               Etiquetas mensuales aisladas y sensibilidad de negociación
  screening.py            Preparación causal, regresiones HAC, Holm, terciles y sombras
  validation.py           Calendario CPCV, purga, embargo y recuentos por regla
data/raw/                Originales locales (fuera de Git)
data/processed/          Tablas Parquet y resúmenes JSON (fuera de Git)
outputs/diagnosis/       Tablas del diagnóstico (fuera de Git)
tests/                   Comprobaciones esenciales sin red
docs/                    Decisiones y hallazgos para documentar el TFM
```

Los JSON describen los resultados y sus supuestos: no se editan para dirigir la ejecución. Las tablas mantienen nombres fijos. Volver a preparar Shiller retira señales, componentes, características, etiquetas y simulaciones anteriores; preparar French retira componentes, etiquetas y simulaciones, conservando señales. Los cuadernos 03–06 guardan sus propios resultados sin sobrescribirse entre sí. Regenerar señales, componentes o características retira también el conjunto etiquetado; vuelve a ejecutar el 08. Regenerar sus entradas, incluidas las etiquetas, retira las cinco tablas `screening_*` y sus informes; vuelve a ejecutar el 09. Esas mismas preparaciones retiran también las dos tablas `validation_*` y sus informes; vuelve a ejecutar el 10. Repetir el 09 no las invalida. Un fallo de publicación restaura las salidas anteriores de esa tabla.

Los originales se reutilizan y no se sustituyen automáticamente. No se modifican los datos históricos conservados al actualizar el código. Si falta una tabla, ejecuta el cuaderno que la prepara. Si regeneras 01 o 02, vuelve a ejecutar las simulaciones que necesites. No se requiere servidor ni base de datos.

## Verificación

```bash
python -m pytest -q
```

Las pruebas revisan fuentes, fechas, fórmulas financieras y el recorrido de preparación y simulación sin red ni datos del usuario. El recorrido de notebooks requiere las dependencias opcionales indicadas. Antes de hacer commit, usa **Clear All Outputs** y guarda los cuadernos. Más detalles en [notebooks/README.md](notebooks/README.md) y [tests/README.md](tests/README.md).
