# Comparación cronológica con y sin régimen

Diseño fijado el 15 de noviembre de 2026, tras revisar la guía de esa fecha y conocer los experimentos CPCV de los notebooks 11–13. No es un prerregistro anterior a toda exploración. El notebook 14 implementa las referencias M0/M1 y, en una segunda parte, su comparación con M2. Esta ampliación se fija después de conocer M0/M1 y antes de calcular M2 con los datos reales. No acepta regímenes ni utiliza datos desde 1990.

## Motivo y escalera prevista

El nuevo apartado 5 de la guía (pp. 19–21) pide demostrar que el régimen mejora un modelo sin él, con las mismas fechas, parámetros y condiciones. El walk-forward de descubrimiento aportará la evidencia cronológica; CPCV complementará la robustez. El periodo final desde 1990 se reserva para una ejecución posterior con el procedimiento fijado.

| Modelo | Entradas o referencia | Estado |
|---|---|---|
| M0 | Frecuencia positiva del entrenamiento anual de cada regla | Notebook 14 |
| M1 | Retorno del último mes y momentum 12–1, ambos transformados causalmente | Notebook 14 |
| M2 | M1 + volatilidad de 12 meses + retorno de 24 meses + drawdown de 12 meses | Notebook 14 |
| M3 | M2 + `indicador(retorno_24m < 0) × volatilidad_12m`, estandarizada con historia pasada | Previsto |

«Sin régimen» es una definición operativa: las dos variables de M1 representan información asociada a las señales, pero también pueden describir indirectamente condiciones del mercado. Se utilizan ambas para las dos reglas, sin escoger una lista distinta según resultados. La dirección original de cada regla permanece fija y las fechas, etiquetas y retornos realizados nunca entran como predictores.

Las tres variables directas del núcleo ya existen en la tabla 07. Las diez candidatas se conservan para los experimentos más amplios. M3 no se calcula en este incremento. La hipótesis de su interacción es que la relación entre volatilidad y resultado puede cambiar tras un mercado bajista, sin asumir que la evidencia de momentum transversal se transfiera a nuestro índice. Para momentum se investigará un posible deterioro en ese entorno; para reversión el análisis seguirá siendo exploratorio, sin dirección inequívoca fijada por la literatura revisada. No se ha calculado su rendimiento para decidir esta definición.

Se prevén tres retiradas individuales de M2: sin volatilidad, sin retorno de 24 meses y sin drawdown. La comparación principal será M2 frente a M1, para el conjunto; cada retirada estudiará el aporte adicional de una variable condicionado a las otras. La falta de mejora individual puede reflejar redundancia y no demuestra que la variable carezca de información. Son listas fijas; en esta comparación no se elegirá una lista usando los resultados de sus bloques de prueba. La posterior selección Clustered MDA constituirá otra variante, aprendida dentro del entrenamiento y evaluada por separado.

## Calendario del notebook 14

- Desarrollo conservado: enero de 1927–diciembre de 1989, con el calentamiento causal existente.
- Prueba cronológica: enero de 1950–diciembre de 1989; cuarenta bloques anuales.
- Ventana expansiva y reajuste al comienzo de cada año. Los coeficientes permanecen fijos durante sus doce meses de prueba.
- Purga de un mes objetivo antes del bloque, sobre calendario completo. Para probar 1950 se admiten etiquetas hasta noviembre de 1949 y se excluye diciembre de 1949.
- No hay entrenamiento posterior al bloque probado. El embargo posterior de CPCV no elimina filas en esta separación cronológica; no se impone además una exclusión permanente sobre resultados de años anteriores cuando pasan a ser historia disponible.
- Las características de cada mes siguen calculándose con su pasado, también durante el año de prueba. No se congela la normalización en enero ni se utiliza un escalador global.

1950 es una decisión de diseño del TFM: deja un tramo inicial amplio para aprender y permite un calendario anual sencillo. No es una fecha exigida por la guía ni elegida tras comparar resultados de distintos inicios. Se comprobaron cobertura y clases, sin ajustar modelos: el primer entrenamiento tiene 110 ejemplos de momentum y 230 de reversión; ambos contienen las dos clases. A lo largo de la prueba hay 331 ejemplos de momentum y 479 de reversión. Dos años de momentum no contienen señales utilizables, y otros contienen una única clase.

Cada mes del desarrollo tiene un papel en cada partición: `train`, `purge`, `validation` o `future`. Solo después se filtra por `sample_usable`. Esta marca conserva la disponibilidad de las diez características y el mismo calentamiento de los experimentos anteriores, aunque M1 solo utilice dos columnas. Así se fija una muestra común para futuras comparaciones sin ampliar cada variante con los meses que más le convengan.

No se exige ejecutar 09–13. El 14 reconstruye los ejemplos de 07/08 mediante la preparación ya validada. La logística reutiliza los parámetros y los helpers del 11: L2, C=1, intercepto, `lbfgs`, sin ponderación de clases ni calibración adicional. Se ajustan hasta ochenta logísticas de M1 y ochenta de M2, una por año y regla para cada variante. El optimizador es determinista para estas opciones; no se añade una semilla que no emplea.

## Probabilidades, métricas y disponibilidad

M0 predice la frecuencia positiva de las etiquetas de su propio entrenamiento anual. M1 predice con las dos columnas explícitas. Solo se etiquetan y predicen las señales activas con características disponibles; un mes en efectivo no recibe etiqueta cero ni probabilidad cero. Los meses sin operación permanecen en el calendario y en los recuentos, aunque no sean ejemplos de clasificación.

Cada ejemplo probado recibe una única predicción de cada método. Las métricas principales son AUC y log-loss sobre todas las predicciones cronológicas reunidas por regla (`pooled`). No se promedian cinco probabilidades CPCV ni las AUC de los años. La AUC anual de M0 es 0,5 cuando hay ambas clases; su AUC reunida puede diferir de 0,5 porque su probabilidad varía entre años.

Se conservan las métricas de los cuarenta años para ambas reglas y ambos modelos, aunque un año esté vacío. Con una única clase, la log-loss sigue siendo calculable y AUC queda ausente con `auc_status=single_class`. Sin ejemplos, ambas métricas quedan ausentes. Si falta alguna predicción, no se elimina ese mes para calcular un resultado favorable: la métrica correspondiente queda no disponible. Si el entrenamiento no contiene ambas clases, M1 queda no estimable; M0 conserva su frecuencia cuando exista entrenamiento. Una falta de convergencia detiene y registra el intento, sin cambiar parámetros.

El cuaderno no aplica un umbral de aceptación, construye posiciones ni calcula Sharpe. Las etiquetas siguen siendo las operaciones aisladas netas frente a RF del 08; no se capitalizan como una cuenta continua. Tampoco se declara superada una puerta de capacidad predictiva por una AUC aislada. El estado de M0/M1 conserva `pending_regime_comparisons_shadows_and_economic_evaluation` como alcance de su referencia inicial; el informe específico de M2 concreta las comprobaciones pendientes.

## Contrastes posteriores ya previstos

La aportación del conjunto M2 se medirá con `AUC(M2) − AUC(M1)` sobre las mismas observaciones. Sus sombras desplazarán conjuntamente solo las variables añadidas, manteniendo las señales, etiquetas, fechas y M1. Se repetirá el aprendizaje bajo esas referencias. Las retiradas individuales y la interacción tendrán contrastes correspondientes; una interacción deberá reconstruirse coherentemente a partir de sus entradas desplazadas. El protocolo específico de desplazamientos se concretará antes de ejecutarlos. Las sombras de los notebooks 09/12/13 no se transfieren automáticamente a este contraste.

Se exigirá mejora de AUC, comparación superior al percentil 95 de sus sombras, mejora en una mayoría estricta de los periodos previstos y Sharpe neto superior a las referencias exigidas por la guía. Los periodos no estimables permanecerán en el denominador previsto y no contarán como mejoras: para cuarenta periodos anuales se necesitan al menos veintiuno favorables; para las quince particiones CPCV, al menos ocho. Se mostrarán también los recuentos estimables. Las particiones no son ensayos independientes.

La log-loss seguirá describiendo la calidad de las probabilidades y se mantendrá en la puerta general y en Clustered MDA. La guía conserva esas funciones aunque centra la aceptación incremental en AUC y utilidad económica. Los contrastes por variable y familia no se presentarán como un control conjunto demostrado del error. DSR/PBO requerirán registrar todas las variantes realmente probadas y sus series económicas; las referencias sintéticas y los años no son configuraciones independientes.

Solo se construirán mapas SHAP de regímenes aceptados, usando observaciones de prueba y selección interna cuando corresponda. Los nuevos modelos no heredarán la aceptación de una logística anterior. Un resultado nulo seguirá siendo válido.

## Archivos e integración

La [estructura de entrega](estructura_notebooks.md) integrará este recorrido en el cuaderno final de modelado. M2 amplía el notebook 14 por secciones; M3 se incorporará después sin crear un cuaderno por cada modelo. Este cambio de organización no modifica el protocolo científico.

`src/tfm/walk_forward.py` mantiene el calendario, los recuentos, los ajustes y las métricas. Reutiliza `fit_partition` y `prepare_validation_samples`, sin modificar su comportamiento. El notebook `14_referencia_walk_forward.ipynb` explica cada bloque y publica cinco tablas con JSON descriptivos:

| Tabla | Contenido |
|---|---|
| `walk_forward_splits` | 30.240 filas: cuarenta particiones sobre los 756 meses completos. |
| `walk_forward_summary` | Ochenta años/reglas, con disponibilidad, clases y estado del ajuste. |
| `walk_forward_predictions` | Una fila por ejemplo probado, con probabilidades de M0/M1. |
| `walk_forward_metrics` | 160 métricas anuales y cuatro reunidas; se conservan vacíos y clases únicas. |
| `walk_forward_coefficients` | Intercepto y dos coeficientes por año y regla, con estado. |

Antes de ajustar se registra el intento en `outputs/experiments/walk_forward_trials.jsonl`, con listas de columnas, parámetros, calendario y guía. Se conserva terminación, métricas o fallo. M1 cuenta como una configuración por regla, no como cuarenta; M0 es su referencia. Una repetición idéntica es otro intento de la misma variante. Los historiales anteriores no se modifican.

Recalcular entradas de 01, 02, 07 u 08 retira estas cinco tablas; recalcular 09–13 las conserva. El 14 no sustituye sus resultados. Las publicaciones siguen el patrón de tabla y JSON: si falla su celda, debe repetirse completa. No se añaden dependencias, CLI, configuraciones o CSV. La memoria se actualizará por separado y manualmente.

## Ampliación M2: comparación directa del bloque de régimen

La segunda parte conserva M1 y añade las tres columnas `z_price_volatility_12m`, `z_market_return_24m` y `z_drawdown_12m`, en ese orden. M2 tiene cinco predictores, con idénticos C, solver, etiquetas, costes, años y exclusiones. No selecciona grupos ni incorpora aún M3 o retiradas individuales. La comparación estudia el bloque conjunto, no la aportación individual de cada variable.

Antes de ajustar se leen las cinco tablas publicadas de M0/M1. Se contrastan sus parámetros, fechas, entorno, intento, cobertura y métricas con las entradas actuales. M2 ajusta únicamente sus ochenta modelos; no vuelve a ajustar la referencia ni modifica sus archivos. El notebook completo sí recalcula primero M1 en su sección original y publica su referencia antes de ejecutar M2.

Se comprueba que coinciden exactamente las claves de año, regla, mes y etiqueta y las probabilidades ingenuas de ambos recorridos. Se reúne una predicción de cada método por ejemplo. Una comparación con fechas, clases o recuentos distintos se rechaza; las probabilidades ausentes no se eliminan para calcular una mejora. La diferencia de AUC es `AUC(M2) − AUC(M1)` y la mejora de log-loss es `log_loss(M1) − log_loss(M2)`: en ambos casos, una cifra positiva es favorable.

Se conservan ochenta comparaciones anuales y dos reunidas. El informe muestra por regla cuarenta años previstos, años con AUC estimable, mejoras, empeoramientos, empates y no estimables. La mayoría necesita veintiún años favorables; los no estimables no se borran del total ni se consideran empates estimados. Esa condición describe únicamente la estabilidad: no equivale a aceptación del régimen.

Se guardan cuatro tablas adicionales con JSON:

| Tabla | Contenido |
|---|---|
| `walk_forward_regime_predictions` | Probabilidades originales M0/M1 y M2, emparejadas en las mismas filas. |
| `walk_forward_regime_metrics` | Ochenta métricas anuales y dos reunidas de M2, incluidos años no estimables. |
| `walk_forward_regime_coefficients` | Intercepto y cinco coeficientes de cada año y regla, con estado del ajuste. |
| `walk_forward_regime_comparison` | Diferencias M2–M1 de AUC y M1–M2 de log-loss, con disponibilidad y mejora anual. |

Su informe identifica `reference_attempt` y `reference_variant`, además de su propia variante e intento. Comparte `outputs/experiments/walk_forward_trials.jsonl`; M2 cuenta como una nueva configuración por regla, no como ochenta. Se registran inicio, resultado o fallo, también cuando M2 empeora. La referencia debe estar actualizada antes del primer ajuste. Volver a publicar cualquiera de sus cinco tablas retira las cuatro salidas de M2. Las preparaciones de 01/02/07/08 retiran ambas familias; repetir 09–13 no las invalida. El historial permanece.

El estado de M2 es `pending_matched_cpcv_regime_shadows_and_economic_evaluation`. La robustez CPCV equivalente, sus sombras específicas, M3, retiradas individuales, selección interna, interpretación y utilidad económica siguen pendientes. Una mejora de AUC, por sí sola, no acepta el régimen.

## Límites y comprobaciones esenciales

El orden cronológico evita entrenar con resultados posteriores al bloque de prueba, pero no convierte las medias mensuales en cierres ejecutables ni certifica los dividendos y las revisiones como datos conocidos en cada fecha. La exclusión del último mes es una separación conservadora, no una solución a la interpolación histórica. Se conserva la interpretación retrospectiva y no se presenta como una simulación ejecutable o point-in-time.

Las pruebas comprobarán fronteras, ausencia de entrenamiento futuro, independencia respecto a etiquetas de prueba, invariancia frente a cambios posteriores al corte, métricas verificables y conservación de años vacíos o con una clase. El recorrido completo del notebook se probará con tablas sintéticas, sin red, junto a persistencia, historial e invalidaciones. La ejecución real conservará las entradas y salidas anteriores.

Referencia principal: guía del tutor `Guia TFM ML gestion Inversiones L1 v26-27 (15 11 26).pdf`, pp. 18–21 y tabla temporal de p. 2. Las reglas de preparación y etiquetado permanecen en `caracteristicas.md`, `etiquetado.md` y `hipotesis_y_cribado.md`. La definición anterior de CPCV está en `plan_validacion_temporal.md`. No se incorpora una metodología bibliográfica nueva ni código externo.

## Primera ejecución y verificación

Se ejecutó el notebook completo en un proceso limpio, con datos locales y descargas bloqueadas. Completó los ochenta ajustes sin cambiar parámetros. Se guardaron 30.240 filas de calendario, ochenta resúmenes, 810 ejemplos probados (331 de momentum y 479 de reversión), 164 métricas y 240 coeficientes incluyendo interceptos. Las tablas guardadas coinciden exactamente con las calculadas. Los 66 archivos anteriores comprobados, incluido el notebook 13 con sus cambios locales previos, permanecieron intactos.

| Regla | Log-loss M0 | Log-loss M1 | AUC M0 | AUC M1 |
|---|---:|---:|---:|---:|
| Momentum | 0,684939 | 0,669000 | 0,497251 | 0,595625 |
| Reversión | 0,661412 | 0,644959 | 0,416244 | 0,630296 |

M1 mejora las métricas reunidas frente a M0 en este desarrollo cronológico. No es evidencia de aportación del régimen ni de rentabilidad, y no permite comparar directamente con las métricas CPCV de 11–13: cambian los ejemplos evaluados y el procedimiento de entrenamiento. No se han modificado el año inicial, las variables o los parámetros tras observar estos resultados.

Se reconstruyeron las probabilidades con los coeficientes guardados, con diferencia exactamente cero, y se comprobaron las frecuencias anuales de M0 y las log-loss mediante un cálculo independiente. Se revisaron los gráficos; los meses aislados se muestran con puntos y los meses sin ejemplo quedan como huecos. El notebook se conserva sin salidas ni contadores de ejecución.

Pasan las 66 pruebas del proyecto, incluidas las tres nuevas. Las dos advertencias corresponden a gráficos no interactivos del notebook 09 y no son fallos de este incremento.

## Ejecución de la ampliación M2

Se ejecutó el notebook ampliado en un proceso limpio, con datos locales y descargas bloqueadas. Los ochenta ajustes de M2 completaron el recorrido sin cambiar parámetros. Las cinco tablas de referencia M0/M1 se reprodujeron exactamente frente a su ejecución anterior. Se publicaron 810 predicciones emparejadas, 82 métricas de M2, 480 coeficientes y 82 comparaciones, con sus JSON. Los otros 65 archivos anteriores comprobados permanecieron intactos; el historial añadió los intentos de la repetición de M1 y de la nueva variante M2.

| Regla | AUC M1 | AUC M2 | Diferencia de AUC | Log-loss M1 | Log-loss M2 | Años con mejora de AUC / previstos |
|---|---:|---:|---:|---:|---:|---|
| Momentum | 0,595625 | 0,594764 | −0,000860 | 0,669000 | 0,673069 | 10 / 40 |
| Reversión | 0,630296 | 0,635839 | +0,005543 | 0,644959 | 0,644421 | 17 / 40 |

Momentum tiene 32 años con AUC estimable: diez mejoran, nueve empeoran y trece empatan. Ocho no son estimables. Reversión tiene 39: diecisiete mejoran, siete empeoran y quince empatan; uno no es estimable. Los empates de AUC no implican probabilidades o log-loss idénticas.

El bloque de régimen empeora ligeramente el resultado reunido de momentum y mejora el de reversión. Ninguna regla alcanza la mayoría de veintiún años favorables fijada en el protocolo. Por tanto, esta comparación no acredita la aceptación del bloque de régimen. No se han cambiado variables, parámetros, años o el denominador para alterar la conclusión. Las sombras específicas, la comparación CPCV equivalente y la utilidad económica siguen pendientes, al igual que M3 y las retiradas individuales. No se atribuye este resultado conjunto a cada variable por separado.

Se reconstruyeron las probabilidades de M2 con sus coeficientes guardados, con diferencia exactamente cero. Se contrastaron las log-loss con su fórmula directa y las AUC anuales y reunidas mediante comparaciones entre pares de etiquetas, conservando los años no estimables. Las tablas persistidas coinciden exactamente con las calculadas. El notebook se entrega sin salidas ni contadores.

Pasan las 66 pruebas del proyecto. Se ampliaron las tres comprobaciones de walk-forward para cubrir M2 y su integración, sin añadir otra colección de tests. Las dos advertencias del recorrido gráfico del 09 permanecen sin cambios.
