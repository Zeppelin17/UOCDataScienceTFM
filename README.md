# UOC Data Science TFM

Estudio de aprendizaje automático como filtro de las señales de momentum y reversión. El desarrollo utiliza datos mensuales de **1927–1989**; la evaluación desde 1990 sigue pendiente y deshabilitada.

El trabajo se ejecuta mediante **notebooks**, sin CLI ni archivos de configuración. Los cuadernos muestran las fuentes, los periodos y los supuestos; las funciones reutilizables están en `src/tfm`.

Para comprender el estudio desde cero, abre la [guía interactiva del proyecto](docs/guia_del_proyecto.html) en un navegador. Recorre los fundamentos y los notebooks 00–10, con ejemplos, detalles de fórmulas y código y un glosario. [Instrucciones de lectura](docs/guia_del_proyecto.md).

## Cómo empezar

Con Python 3.11 o posterior, desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,notebooks,models]"
```

En PowerShell, activa el entorno con `.venv\Scripts\Activate.ps1`. El extra `models` añade scikit-learn para el notebook 11; si ya tenías el entorno de notebooks, incorpora ese extra con `python -m pip install -e ".[models]"`. Los notebooks 01–10 no lo necesitan. `requirements-lock.txt` conserva las versiones verificadas del flujo base, pytest y modelado; las dependencias opcionales de notebooks se instalan por separado.

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
| [09 Cribado](notebooks/09_cribado_regimen.ipynb) | Relaciona el retorno de cada regla con las diez variables; revisa BH al 10 %, terciles, subperiodos y sombras | Haber ejecutado 01 → 02 → 07 → 08 |
| [10 Validación temporal](notebooks/10_validacion_temporal.ipynb) | Prepara quince particiones CPCV con purga y embargo y cuenta ejemplos por regla | Haber ejecutado 01 → 02 → 07 → 08; independiente del 09 |
| [11 Regresión logística](notebooks/11_regresion_logistica.ipynb) | Compara probabilidades L2 con la frecuencia de éxitos del entrenamiento | Haber ejecutado 01 → 02 → 07 → 08 → 10; extra `models` |
| [12 Sombras de la logística](notebooks/12_sombras_logistica.ipynb) | Compara el modelo original con 642 rotaciones conjuntas de las características | Tablas completas del 11 y sus entradas; extra `models` |
| [13 Selección de grupos](notebooks/13_seleccion_clustered_mda.ipynb) | Selecciona con Clustered MDA dentro del entrenamiento y evalúa la logística en bloques exteriores | Tablas del 11 y sus entradas; extra `models` |

El 00 puede ejecutarse por separado. Para reproducir las simulaciones, ejecuta 01 → 02 → 03–06. Los cuadernos 03–06 no necesitan ejecutarse entre sí. El 07 prepara diez características candidatas y no necesita las simulaciones ni el 02. Conserva 756 meses, de los que 749 tienen las diez variables completas. El 08 genera etiquetas centrales y una sensibilidad sin negociación, conservando las mismas filas. El 09 implementa el cribado descrito en [Hipótesis y protocolo](docs/hipotesis_y_cribado.md), con preparación causal y una muestra común tras su calentamiento. Es descriptivo: no selecciona automáticamente variables ni estima habilidad fuera de muestra.

El 10 implementa el [diseño de validación temporal](docs/plan_validacion_temporal.md): seis bloques, quince combinaciones, purga de un mes y embargo de seis meses. Separa el calendario de los ejemplos utilizables por regla, conserva las diez candidatas y no entrena modelos. Guarda las particiones y sus recuentos, sin depender de los resultados del cribado.

El 11 implementa el [primer experimento de logística L2](docs/primer_modelo.md), con las diez candidatas, `C=1` y sin ponderación de clases ni búsqueda de parámetros. Guarda las cinco predicciones de validación por ejemplo y su media mensual, log-loss/AUC y coeficientes. La referencia es la frecuencia positiva del entrenamiento. El historial de intentos está en `outputs/experiments/logistic_trials.jsonl`. Su puerta de capacidad predictiva se concreta en el 12. La selección de grupos se desarrolla en el 13; SHAP y la evaluación económica del filtro vendrán después. La guía interactiva cubre los fundamentos y notebooks 00–10; los posteriores incluyen sus propias explicaciones.

El 12 implementa el [protocolo de sombras del modelo](docs/sombras_logistica.md). Desplaza juntas las diez características sobre los 713 meses comunes, conservando etiquetas, señales y particiones, y repite los ajustes para 642 desplazamientos con distancia circular mínima de 36 meses. Compara la mejora de log-loss original con el percentil 95 de las sombras; la AUC de las sombras es descriptiva. El criterio operativo se fija tras conocer el 11 y antes de calcular las sombras. No equivale a un contraste exacto o a demostrar rentabilidad. Guarda dos tablas y un historial separado en `outputs/experiments/logistic_shadow_trials.jsonl`, conservando las salidas originales del 11.

El 13 aplica la [selección interna mediante Clustered MDA](docs/seleccion_clustered_mda.md). Reserva el último bloque de cada entrenamiento exterior para seleccionar, agrupa con Spearman absoluto y enlace completo (umbral 0,70) sobre los otros tres, mide el aumento de log-loss al permutar cada grupo treinta veces y conserva los grupos con media positiva. Después reajusta con todo el entrenamiento exterior y evalúa sus bloques reservados. Si no queda ningún grupo, usa solo el intercepto. Guarda cinco tablas `mda_*` y el historial de la variante, sin modificar 11/12. La selección es específica de esta logística; sus sombras, otros modelos y la utilidad económica siguen pendientes. SciPy se declara como dependencia directa de modelado y ya estaba instalada con scikit-learn.

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
  screening.py            Preparación causal, regresiones HAC, BH, terciles y sombras
  validation.py           Calendario CPCV, purga, embargo y recuentos por regla
  logistic.py             Primer clasificador L2, probabilidades y registro de variantes
  model_shadows.py        Rotaciones conjuntas y comparación del modelo con sus sombras
  clustered_mda.py        División interna, grupos e importancia para la logística seleccionada
data/raw/                Originales locales (fuera de Git)
data/processed/          Tablas Parquet y resúmenes JSON (fuera de Git)
outputs/diagnosis/       Tablas del diagnóstico (fuera de Git)
outputs/experiments/     Historial científico de intentos de modelado (fuera de Git)
tests/                   Comprobaciones esenciales sin red
docs/                    Decisiones y hallazgos para documentar el TFM
```

Los JSON describen los resultados y sus supuestos: no se editan para dirigir la ejecución. Las tablas mantienen nombres fijos. Volver a preparar Shiller retira señales, componentes, características, etiquetas y simulaciones anteriores; preparar French retira componentes, etiquetas y simulaciones, conservando señales. Los cuadernos 03–06 guardan sus propios resultados sin sobrescribirse entre sí. Regenerar señales, componentes o características retira también el conjunto etiquetado; vuelve a ejecutar el 08. Regenerar sus entradas, incluidas las etiquetas, retira las cinco tablas `screening_*` y sus informes; vuelve a ejecutar el 09. Esas mismas preparaciones retiran también las dos tablas `validation_*` y sus informes; vuelve a ejecutar el 10. Repetir el 09 no las invalida. Un fallo de publicación restaura las salidas anteriores de esa tabla.

Los originales se reutilizan y no se sustituyen automáticamente. No se modifican los datos históricos conservados al actualizar el código. Si falta una tabla, ejecuta el cuaderno que la prepara. Si regeneras 01 o 02, vuelve a ejecutar las simulaciones que necesites. No se requiere servidor ni base de datos.

Regenerar entradas de 01, 02, 07 u 08, o guardar las particiones del 10, retira también las cuatro tablas `logistic_*` y sus informes. Repetir el 09 las conserva. El historial científico se mantiene aunque se recalculen las tablas; repetir una variante no la convierte en otra configuración. Las medias de probabilidades no son trayectorias de rentabilidad para DSR/PBO.

Recalcular cualquiera de las cuatro tablas del 11 retira también `logistic_shadows` y `logistic_shadow_comparison`, con sus JSON. Sus entradas anteriores las retiran igualmente; el cribado 09 las conserva. Los historiales de intentos permanecen intactos. El 12 requiere la familia completa de sombras para calcular sus umbrales y muestra el progreso cada 25 rotaciones.

Recalcular entradas de 01, 02, 07, 08, 10 u 11 retira también las cinco tablas `mda_*` y sus JSON. Repetir 09 o 12 las conserva: no son entradas de esta selección. Su historial está en `outputs/experiments/clustered_mda_trials.jsonl` y no se elimina al preparar datos. La frecuencia de selección entre particiones es descriptiva y no fija una lista global retrospectiva de variables.

## Verificación

```bash
python -m pytest -q
```

Las pruebas revisan fuentes, fechas, fórmulas financieras y el recorrido de preparación y simulación sin red ni datos del usuario. El recorrido de notebooks requiere las dependencias opcionales indicadas. Antes de hacer commit, usa **Clear All Outputs** y guarda los cuadernos. Más detalles en [notebooks/README.md](notebooks/README.md) y [tests/README.md](tests/README.md).
