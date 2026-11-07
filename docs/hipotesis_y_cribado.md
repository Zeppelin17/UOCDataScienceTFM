# Hipótesis y protocolo de cribado

Fecha: 7 de noviembre de 2026. Estado: protocolo definido antes de calcular relaciones predictivas e implementado en el notebook 09. Se conserva el diseño fijado antes de los contrastes. No añade configuraciones ni modifica las reglas, fuentes, etiquetas o costes.

## 1. Qué queremos comprobar

El cribado desarrolla H1 de la memoria: si el resultado de cada regla cambia según el entorno anterior. H2 y H3 —utilidad económica del filtro frente a las alternativas— se comprobarán después, con modelos y simulaciones fuera de muestra. Encontrar una asociación aquí no demuestra esas dos hipótesis.

Ya se han examinado cobertura, precios, señales, simulaciones y conteos y sensibilidad de etiquetas. Por tanto, este registro es anterior a los contrastes predictivos, pero no anterior a toda exploración del desarrollo. Se conservarán también resultados negativos y decisiones descartadas.

El ámbito es exclusivamente 1927–1989. El tramo desde 1990 no se utilizará para elegir características, transformaciones o modelos. Las consultas de datos posteriores realizadas en fases anteriores siguen documentadas: no se describirá ese tramo como completamente desconocido.

## 2. Hipótesis por característica

Todas se refieren al resultado del mes siguiente. Las fórmulas y los retrasos permanecen en [caracteristicas.md](caracteristicas.md): precios hasta la decisión y crédito/industrias con un mes adicional de retraso. Se mantienen diez candidatas, sin añadir transformaciones como nuevas características en este paso.

`+` significa esperar una pendiente positiva sobre el retorno de la regla. `Sin signo` significa un contraste exploratorio bilateral, no esperar efecto cero. Un signo esperado es una hipótesis de este TFM, no una conclusión probada para nuestro índice.

| Característica | Momentum | Reversión | Mecanismo y alcance de la hipótesis |
|---|---|---|---|
| `price_return_1m` | Sin signo | Sin signo | El último movimiento puede reflejar continuación o corrección. En reversión su signo ya determina la dirección; una pendiente sobre el retorno firmado no contrasta que movimientos más grandes reviertan más. |
| `momentum_12_1` | + | Sin signo | Una tendencia previa más favorable podría acompañar mejores resultados de continuación. También determina si momentum propone operar, por lo que puede reflejar activación de la regla. |
| `market_return_24m` | + | Sin signo | Un entorno previo de subida podría ser más favorable al momentum que uno bajista. Se inspira en el estudio de estados de mercado, adaptado a nuestro índice y sin garantizar una relación lineal. |
| `distance_ma_12m` | + | Sin signo | Estar más por encima de la media podría describir una tendencia favorable a la continuación. Es una hipótesis conceptual; puede repetir información de otros indicadores. |
| `price_volatility_12m` | Sin signo | Sin signo | Más volatilidad describe mayor riesgo reciente, pero no obliga a que la rentabilidad media aumente o disminuya. La evidencia sobre caídas de momentum y liquidez justifica estudiarla, sin confundir riesgo con media. |
| `drawdown_12m` | + | Sin signo | Un valor más cercano a cero describe menor caída desde el máximo y podría favorecer la continuación. No anticipa por sí solo un rebote. |
| `credit_spread_pp` | Sin signo | Sin signo | El nivel del diferencial aproxima tensión crediticia, que puede alterar riesgos y primas exigidas. No fija inequívocamente el resultado de cada regla. |
| `credit_spread_change_pp` | Sin signo | Sin signo | El aumento del diferencial describe deterioro reciente del entorno crediticio; su efecto sobre beneficios de continuación o corrección es exploratorio. |
| `industry_breadth_12m` | + | Sin signo | Una subida extendida entre industrias podría respaldar una tendencia del índice. Es una hipótesis conceptual sobre carteras industriales, no amplitud observada de sus componentes. |
| `industry_dispersion` | Sin signo | Sin signo | Mayor dispersión puede reflejar heterogeneidad o tensión. No equivale a volatilidad del índice ni implica una dirección de rentabilidad. |

La reversión de un índice no hereda automáticamente los resultados de estrategias transversales entre acciones o de frecuencia diaria. Por eso sus diez relaciones se mantienen exploratorias. No se añadirá `abs(price_return_1m)`, una interacción con la posición o una división entre compras y cortos después de ver qué variante funciona: si se propone esa ampliación, se documentará como una hipótesis nueva y se contará entre los intentos.

La motivación de estados de mercado se apoya en Cooper, Gutierrez y Hameed (2004) y Daniel y Moskowitz (2016); la relación entre reversión y liquidez, en Nagel (2012). Sus universos y frecuencias no son réplicas de este trabajo. Referencias ya presentes en la memoria: `bib:cooper2004`, `bib:daniel2016`, `bib:nagel2012`.

## 3. Qué retorno usará el cribado

Para cada regla se calculará la serie **sin filtrar, con posiciones conservadas entre meses**, mediante el simulador existente y los supuestos centrales visibles en el notebook 08. Se simulará el calendario completo antes de seleccionar fechas, para no reiniciar cuentas por tercil o subperiodo.

La respuesta será el exceso mensual neto frente al efectivo:

`r_anomalia[t] = retorno_neto_regla_sin_filtrar[t] − RF[t]`

El ajuste será `r_anomalia[t] = a + b · z_caracteristica[t] + error[t]`. La característica de esa fila solo contiene información anterior al resultado. Se conserva la respuesta mensual sin dividirla por una volatilidad estimada, siguiendo la ecuación específica de cribado de 1.B; no se incorpora en este paso un segundo objetivo EWMA de la receta general de la guía.

Este retorno no es `excess_return` del etiquetado aislado ni una etiqueta binaria. Para los modelos se mantendrán las etiquetas del 08 y sus meses con señal. El cribado central, en cambio, conserva también los meses de efectivo: describe la regla completa. Se informará de la frecuencia de señales por régimen, ya que una asociación puede deberse a que la regla opera más y no a que acierte más cuando opera. Los costes de salida pueden aparecer en un mes sin nueva exposición.

## 4. Preparación y muestra común

Decisión del TFM dentro de la orientación de la guía: calentamiento de **36 observaciones mensuales anteriores válidas por característica**, sin rellenar ausencias. Para cada fecha se calculan los percentiles 1 y 99 de su historia anterior, se recorta a esos límites y se obtiene un z-score usando la media y desviación típica muestral de esa historia recortada con los mismos límites. El valor actual no entra en el cálculo de esos estadísticos.

No se winsorizan los resultados de las estrategias: se conservan las pérdidas extremas. Si la historia no alcanza el mínimo o su desviación es nula, la transformación queda ausente. Se utiliza el mismo tramo mensual completo para las diez variables y ambas reglas; el informe mostrará las fechas y los motivos de exclusión. Ante huecos interiores se revisará su causa, sin comprimir el calendario para llamar «meses» a filas separadas.

Este cálculo causal describe cada observación con información pasada de las características, sin usar etiquetas. No es un escalado ajustado con todo el desarrollo. En los modelos, cualquier ajuste adicional aprendido, selección de variables o formación de compuestos se realizará exclusivamente con el entrenamiento de cada partición. El protocolo detallado de esas particiones será el incremento posterior; no se implementa ahora CPCV.

## 5. Contrastes y comprobaciones fijados

| Comprobación | Decisión para este TFM |
|---|---|
| Regresión principal | Una regresión con intercepto por característica y regla: 20 en total. Errores HAC de Newey–West, ponderación Bartlett y **6 retardos mensuales** fijados por adelantado, sin factor de corrección de muestra pequeña `n/(n−2)`. No se buscará el retardo que dé significación. |
| Inferencia | Contraste bilateral `b = 0`, con aproximación normal asintótica para los valores p. Reportar coeficiente, error estándar, estadístico y valor p; las garantías HAC son asintóticas y no eliminan no estacionariedad o sesgo de selección. |
| Multiplicidad | **Holm al 5 % sobre la familia conjunta de 20 pruebas**, no diez por separado ni solo las favorables. Un contraste no estimable se identifica y conserva en la familia con p = 1 a efectos de ajuste, sin presentarlo como una estimación de efecto cero. |
| Dirección | Donde hay `+`, una pendiente negativa no respalda la hipótesis aunque sea significativa. Para las exploratorias se informa del signo observado sin convertirlo retrospectivamente en una predicción previa. |
| Terciles | Cortes de un tercio y dos tercios calculados con la historia anterior de cada variable, con el mismo mínimo de 36 observaciones. Ante cortes coincidentes, no se separan empates artificialmente para forzar tres grupos. Mostrar conteos, frecuencia de señales, media y Sharpe descriptivo del exceso de la regla. |
| Estabilidad | Cuatro tramos fijos: 1927–1942, 1943–1958, 1959–1974 y 1975–1989, limitados a la muestra utilizable. Informar pendientes y cobertura; no elegir después los años que conservan el signo. No se añaden pruebas de significación por subperiodo. |
| Sombras circulares | Desplazar conjuntamente las diez series ya transformadas sobre el tramo mensual común. Usar todos los desplazamientos cuyo recorrido circular mínimo sea **36 meses**: `min(s, N−s) >= 36`. Mantener fijos retornos y fechas. No permutar filas individualmente. |
| Comparación con sombras | Para cada desplazamiento calcular el máximo de `abs(t_HAC)` entre las 20 relaciones. Comparar cada estadístico real con el percentil 95 de esos máximos, con cuantiles por orden superior. Así no se elige la sombra más favorable ni se ignora que se miran varias variables. |

Los seis retardos HAC, los 36 meses, los cuatro subperiodos y la familia conjunta son elecciones metodológicas del TFM, no cifras obligatorias de la guía. La guía admite Holm o BHY y sombras separadas al menos 24–36 meses; aquí se fijan Holm y 36. El umbral orientativo `t ≈ 2,8` para diez candidatas no sustituye al ajuste real de nuestra familia de veinte.

Las sombras son una comprobación de plausibilidad, no un valor p exacto: desplazar series no garantiza intercambiabilidad en mercados que cambian con el tiempo. La unión circular crea una frontera artificial y tampoco demuestra causalidad. Su resultado se interpretará junto con el contraste HAC y la estabilidad, sin elegir entre procedimientos según cuál resulte favorable.

El Sharpe por tercil resume meses que pueden estar separados: se indicará la convención mensual anualizada por raíz de doce y el número de meses. No se capitalizarán esos retornos para presentar una estrategia negociable. Los gráficos no incluyen nuevos contrastes formales ni una búsqueda de cortes óptimos.

## 6. Cómo se utilizarán los resultados

La tabla distinguirá: relación no estimable, exploratoria sin respaldo, signo contrario a la hipótesis, asociación que supera Holm y asociación que además destaca frente a las sombras. Se mostrarán también los terciles y los cuatro subperiodos; no se ocultarán contradicciones ni se reducirán a una puntuación de éxito inventada después.

El cribado completo de 1927–1989 es **descriptivo del desarrollo**. No se utilizará su lista de ganadoras para presentar después como independiente una validación CPCV sobre las mismas observaciones. Si un criterio de selección usa retornos o etiquetas, se repetirá dentro del entrenamiento de cada partición. Clustered MDA se calculará sobre validación interna del entrenamiento antes de evaluar el bloque exterior. El esquema de selección anidada se concretará antes de los modelos.

Una pendiente lineal no significativa tampoco descarta automáticamente una relación no lineal. Las diez candidatas seguirán identificadas y cualquier evaluación posterior de logística, random forest o boosting conservará la separación entre selección y evaluación. EBM se mantiene como ampliación condicionada, no se añade aquí.

No se retocarán reglas, ventanas, signos, cortes o costes para obtener respaldo. Si el cribado no encuentra relaciones robustas, se documentará. La mejora económica solo podrá afirmarse después de evaluar el filtro frente a los comparadores con el protocolo correspondiente.

## 7. Implementación y salidas

El notebook `09_cribado_regimen.ipynb` requiere **01 → 02 → 07 → 08**. Muestra estas decisiones, construye la respuesta y las transformaciones y produce los veinte contrastes, terciles, estabilidad y sombras. Los cálculos reutilizables están en `src/tfm/screening.py`, sin CLI ni configuraciones. Las pruebas esenciales revisan alineación y causalidad, HAC/Holm con una referencia exacta, el rechazo de familias de sombras incompletas y el recorrido persistido del notebook sin red.

La última celda guarda cinco tablas Parquet con sus JSON en `data/processed/`: `screening_monthly` (1512 filas de calendario y sus marcas de disponibilidad), `screening_tests` (20 contrastes), `screening_terciles` (60 grupos, incluidos los vacíos), `screening_stability` (80 combinaciones) y `screening_shadows` (todos los desplazamientos admisibles). Cada informe conserva las exclusiones, parámetros y limitaciones, sin convertirlos en configuración de entrada. Se guardan todas las pruebas, incluidas las no favorables. Cada sombra requiere las veinte regresiones estimables con estadísticos finitos. Si alguna queda incompleta, se conserva su fila y el número estimable, pero su máximo queda ausente. No se sustituye por cero ni se calcula el percentil excluyendo desplazamientos: toda la comparación con sombras se marca no disponible. Holm y los contrastes reales se conservan. Las tablas se publican por separado; si falla la celda de guardado, debe repetirse antes de usar sus salidas. No es un registro de estrategias ganadoras ni una estimación de habilidad fuera de muestra. Regenerar cualquiera de sus entradas retira las cinco tablas y sus informes; no cambia las simulaciones anteriores. Al comenzar a evaluar modelos se añadirá el registro sencillo de variantes y retornos fuera de muestra que requiere la guía.

## 8. Referencias metodológicas para la memoria

Fuente principal del protocolo: guía del tutor del **7 de noviembre de 2026**, tabla inicial de validación y anexo práctico, reglas comunes y apartado 4 de 1.B. El [código revisado de Jansen](referencias_jansen.md) aporta organización y ejemplos; su IC transversal y sus permutaciones no se presentan como nuestro contraste temporal o nuestras sombras.

Estas dos entradas no están aún en la bibliografía del `.tex`. Se dejan preparadas para incorporarlas cuando redactemos el procedimiento; no se ha editado la memoria.

```latex
\item \label{bib:neweywest1987}
Newey, Whitney K.; West, Kenneth D.
\textit{A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix}.
Econometrica, volumen 55, número 3, pp.~703--708, 1987.
Propone un estimador de la matriz de covarianzas robusto a heterocedasticidad y autocorrelación, consistente bajo sus supuestos.
\href{https://doi.org/10.2307/1913610}{DOI: 10.2307/1913610}.

\item \label{bib:holm1979}
Holm, Sture.
\textit{A Simple Sequentially Rejective Multiple Test Procedure}.
Scandinavian Journal of Statistics, volumen 6, número 2, pp.~65--70, 1979.
Propone un procedimiento secuencial para contrastar varias hipótesis controlando la probabilidad de rechazar al menos una hipótesis nula verdadera.
\href{https://www.jstor.org/stable/4615733}{Artículo en JSTOR}.
```

Fuentes consultadas: [versión NBER de Newey–West y datos de su publicación en Econometrica](https://www.nber.org/papers/t0055), [referencia del artículo de Holm en JSTOR](https://www.jstor.org/stable/4615733), [Daniel y Moskowitz (2016)](https://kentdaniel.net/papers/published/jfe_16.pdf). Las extensiones al diseño de este TFM se identifican arriba como decisiones propias.

## 9. Verificación de la implementación

El notebook completo se verificó con los originales locales preparados, sobre una copia temporal y sin descargar fuentes ni modificar los datos del estudiante. El calentamiento deja 713 meses comunes, de agosto de 1930 a diciembre de 1989, y 642 desplazamientos circulares. Los veinte contrastes son estimables. Cuatro asociaciones de momentum superan Holm y la referencia de sombras: retorno del último mes, distancia a la media de doce meses, drawdown y amplitud industrial. La del último mes sigue siendo exploratoria, ya que no se fijó un signo previo. Ninguna relación de reversión supera esos criterios.

Estos resultados no seleccionan variables ni demuestran mejora del filtro. La activación de momentum y el uso de precios medios siguen limitando la interpretación. Se mantienen las diez candidatas y las comprobaciones de terciles y subperiodos. Las pruebas del proyecto cubren el cálculo actual; la referencia HAC exacta, la preparación causal y el recorrido del notebook están incluidos. La respuesta mensual coincide con la del simulador continuo, que no se ha modificado.
