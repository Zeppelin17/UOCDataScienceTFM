# Comparación cronológica con y sin régimen

Diseño fijado el 15 de noviembre de 2026, tras revisar la guía de esa fecha y conocer los experimentos CPCV de los notebooks 11–13. No es un prerregistro anterior a toda exploración. El notebook 14 implementa las referencias M0/M1, su comparación con M2 y la interacción prevista de M3. Esta ampliación se fija después de conocer M0/M1 y antes de calcular M2 con los datos reales. No acepta regímenes ni utiliza datos desde 1990.

## Motivo y escalera prevista

El nuevo apartado 5 de la guía (pp. 19–21) pide demostrar que el régimen mejora un modelo sin él, con las mismas fechas, parámetros y condiciones. El walk-forward de descubrimiento aportará la evidencia cronológica; CPCV complementará la robustez. El periodo final desde 1990 se reserva para una ejecución posterior con el procedimiento fijado.

| Modelo | Entradas o referencia | Estado |
|---|---|---|
| M0 | Frecuencia positiva del entrenamiento anual de cada regla | Notebook 14 |
| M1 | Retorno del último mes y momentum 12–1, ambos transformados causalmente | Notebook 14 |
| M2 | M1 + volatilidad de 12 meses + retorno de 24 meses + drawdown de 12 meses | Notebook 14 |
| M3 | M2 + `indicador(retorno_24m < 0) × volatilidad_12m`, estandarizada con historia pasada | Notebook 14 |

«Sin régimen» es una definición operativa: las dos variables de M1 representan información asociada a las señales, pero también pueden describir indirectamente condiciones del mercado. Se utilizan ambas para las dos reglas, sin escoger una lista distinta según resultados. La dirección original de cada regla permanece fija y las fechas, etiquetas y retornos realizados nunca entran como predictores.

Las tres variables directas del núcleo ya existen en la tabla 07. Las diez candidatas se conservan para los experimentos más amplios. M3 se añade después de conocer M2, manteniendo la fórmula que ya estaba prevista; su convención de historia constante se fija al revisar cobertura y antes de ajustar M3. La hipótesis de su interacción es que la relación entre volatilidad y resultado puede cambiar tras un mercado bajista, sin asumir que la evidencia de momentum transversal se transfiera a nuestro índice. Para momentum se investigará un posible deterioro en ese entorno; para reversión el análisis seguirá siendo exploratorio, sin dirección inequívoca fijada por la literatura revisada. No se ha calculado su rendimiento para decidir esta definición.

Se implementan tres retiradas individuales de M2: sin volatilidad, sin retorno de 24 meses y sin drawdown. La comparación principal será M2 frente a M1, para el conjunto; cada retirada estudiará el aporte adicional de una variable condicionado a las otras. La falta de mejora individual puede reflejar redundancia y no demuestra que la variable carezca de información. Son listas fijas; en esta comparación no se elegirá una lista usando los resultados de sus bloques de prueba. La posterior selección Clustered MDA constituirá otra variante, aprendida dentro del entrenamiento y evaluada por separado.

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

Este primer bloque no aplica un umbral de aceptación, construye posiciones ni calcula Sharpe. Las etiquetas siguen siendo las operaciones aisladas netas frente a RF del 08; no se capitalizan como una cuenta continua. Tampoco se declara superada una puerta de capacidad predictiva por una AUC aislada. El estado de M0/M1 conserva `pending_regime_comparisons_shadows_and_economic_evaluation` como alcance de su referencia inicial; los apartados posteriores documentan los incrementos siguientes.

## Contrastes posteriores ya previstos

La aportación del conjunto M2 se medirá con `AUC(M2) − AUC(M1)` sobre las mismas observaciones. Sus sombras desplazarán conjuntamente solo las variables añadidas, manteniendo las señales, etiquetas, fechas y M1. Se repetirá el aprendizaje bajo esas referencias. Las retiradas individuales y la interacción tendrán contrastes correspondientes; una interacción deberá reconstruirse coherentemente a partir de sus entradas desplazadas. El protocolo específico de desplazamientos se concretará antes de ejecutarlos. Las sombras de los notebooks 09/12/13 no se transfieren automáticamente a este contraste.

Se exigirá mejora de AUC, comparación superior al percentil 95 de sus sombras, mejora en una mayoría estricta de los periodos previstos y Sharpe neto superior a las referencias exigidas por la guía. Los periodos no estimables permanecerán en el denominador previsto y no contarán como mejoras: para cuarenta periodos anuales se necesitan al menos veintiuno favorables; para las quince particiones CPCV, al menos ocho. Se mostrarán también los recuentos estimables. Las particiones no son ensayos independientes.

La log-loss seguirá describiendo la calidad de las probabilidades y se mantendrá en la puerta general y en Clustered MDA. La guía conserva esas funciones aunque centra la aceptación incremental en AUC y utilidad económica. Los contrastes por variable y familia no se presentarán como un control conjunto demostrado del error. DSR/PBO requerirán registrar todas las variantes realmente probadas y sus series económicas; las referencias sintéticas y los años no son configuraciones independientes.

Solo se construirán mapas SHAP de regímenes aceptados, usando observaciones de prueba y selección interna cuando corresponda. Los nuevos modelos no heredarán la aceptación de una logística anterior. Un resultado nulo seguirá siendo válido.

## Archivos e integración

La [estructura de entrega](estructura_notebooks.md) integrará este recorrido en el cuaderno final de modelado. M2 y M3 amplían el notebook 14 por secciones, sin crear un cuaderno por cada modelo. Este cambio de organización no modifica el protocolo científico.

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

El estado de M2 es `pending_matched_cpcv_regime_shadows_and_economic_evaluation`. La robustez CPCV equivalente, las sombras específicas, selección interna, interpretación y utilidad económica siguen pendientes. Las ampliaciones M3 y retiradas individuales se documentan y ejecutan por separado en los apartados siguientes. Una mejora de AUC, por sí sola, no acepta el régimen.

## Ampliación M3: interacción mercado bajista y volatilidad

M3 conserva las cinco columnas de M2 y añade `z_bear_volatility_12m`. El producto original se calcula como `1(market_return_24m < 0) × price_volatility_12m`. El indicador utiliza el signo del retorno de 24 meses original, no el de su z-score; la igualdad a cero no activa el estado bajista. No se utiliza el resultado del mes objetivo ni se prueban otras ventanas.

Se construye una sola serie sobre los 756 meses completos antes de filtrar por señales. Se reutiliza la transformación causal de las otras variables: percentiles 1/99, media y desviación muestral del pasado recortado, con al menos 36 observaciones anteriores. La extracción de esa operación a `transform_feature_series` mantiene exactamente las transformaciones de las diez candidatas originales.

La interacción introduce un caso de escala: al principio su historia es cero. Con un producto no negativo, si el percentil 99 histórico es cero, ambos límites son cero; toda la historia recortada y el valor actual recortado son cero. Se define para esa columna constante una contribución normalizada de cero, sin dividir por cero o asignar una desviación positiva ficticia. La regla también se aplica si la winsorización elimina toda variación de una historia con valores positivos muy escasos. El mínimo de 36 meses no se omite, los valores de origen deben ser finitos y el tratamiento habitual de las diez variables anteriores no cambia. No se imputan datos ausentes.

Esta convención se fija antes de ajustar M3, al comprobar su disponibilidad. Con los datos actuales afecta a enero–octubre de 1930, incluido el primer producto positivo, que el recorte causal todavía lleva a cero. Desde noviembre se observa variación recortada. Se mantienen todos los ejemplos originales de M1/M2, también los tres ejemplos de reversión de agosto–octubre de 1930 que habrían quedado sin z-score por división entre cero. Si faltase realmente la interacción en algún ejemplo de la muestra común, el cálculo se detendría sin eliminarlo.

Los meses cuyo producto original es cero pueden tener z-score negativo una vez que la historia tiene media positiva; esa diferencia de escala no activa el indicador bajista. Los valores original y transformado se muestran juntos en el cuaderno. La hipótesis es permitir una relación distinta con la volatilidad en un mercado bajista; no se supone que la interacción vaya a mejorar este índice.

Se ajustan únicamente ochenta modelos de M3 con los mismos años, etiquetas, exclusiones y parámetros. La lectura de M2 contrasta su intento con M0/M1, sus columnas, métricas y comparación, sin reajustar ni modificar las referencias. La lista permitida de predictores de la logística admite esta única derivada explícita; por defecto sigue utilizando las diez candidatas de los notebooks anteriores. No se añade la interacción a la tabla 07 ni se requieren nuevas fuentes.

Se guardan cuatro tablas: `walk_forward_interaction_predictions` (probabilidades M0–M3 emparejadas), `walk_forward_interaction_metrics` (82 filas de M3), `walk_forward_interaction_coefficients` (560 filas: intercepto y seis columnas por año/regla) y `walk_forward_interaction_comparison` (164 filas: cada año y total para M3 frente a M1 y frente a M2). `reference_model` identifica la comparación; las columnas de referencia se llaman `auc_reference` y `log_loss_reference`.

La comparación M3–M2 estudia añadir la interacción; M3–M1 estudia el bloque de régimen completo. Ambas usan el mismo candidato entrenado y no cuentan como dos configuraciones. El historial registra una nueva variante por regla, su fórmula, convención de escala e intentos de referencia. Republicar M0/M1 retira M2 y M3; republicar M2 retira M3. El resto de entradas anteriores sigue invalidando las tres familias y 09–13 las conserva.

Se mantienen cuarenta años previstos por regla y comparación, con veintiuno favorables como mayoría estricta. El estado es `pending_matched_cpcv_interaction_shadows_and_economic_evaluation`. Las retiradas individuales se desarrollan en el apartado siguiente. Sombras específicas, robustez CPCV, selección interna, SHAP y evaluación económica siguen pendientes. No se cambia la fórmula ni el criterio de estabilidad después de ver M3 y una mejora predictiva no basta para aceptar el régimen.

## Retiradas individuales de M2

La última parte del notebook 14 implementa las tres retiradas ya previstas: sin volatilidad, sin retorno de 24 meses y sin drawdown. Cada candidato conserva las otras cuatro columnas de M2. No se retiran dos variables a la vez ni se incluye la interacción de M3. El módulo `src/tfm/walk_forward_ablation.py` reutiliza el calendario, los ajustes y las métricas de walk-forward; no introduce otro modelo, fuente o configuración de entrada.

Se leen y contrastan las referencias M0/M1/M2 publicadas. Cada retirada se ajusta de nuevo en cada año y regla con los mismos ejemplos, etiquetas, purga y parámetros. Son 240 ajustes adicionales. Esto difiere de Clustered MDA: se elimina la columna y se reentrena, en vez de permutar sus valores manteniendo el modelo fijo. La aportación es condicional a los predictores restantes y a esta logística; la redundancia puede explicar que una variable resulte prescindible sin carecer de información. No es una atribución causal.

La contribución de conservar la variable se define como `AUC(M2 completo) − AUC(sin la variable)` y `log_loss(sin la variable) − log_loss(M2 completo)`. En ambos casos, positivo favorece mantenerla. Es una orientación diferente de las comparaciones de nuevo candidato menos referencia; las columnas se llaman `auc_contribution` y `log_loss_contribution`. Las métricas de cada variante también se guardan para comprobar el signo y los niveles.

Se mantienen los cuarenta años y todos sus estados, incluidos los no estimables. Los recuentos describen contribuciones positivas, negativas, empates y no estimables por regla y variable. La mayoría de veintiún años se muestra como descripción, sin aceptar automáticamente variables o el régimen. Si luego se elige un subconjunto por estos resultados, esa selección deberá repetirse dentro del entrenamiento antes de una evaluación separada. No se toma la mejor retirada y se presenta su resultado en los mismos meses como validación independiente.

Se publican cuatro tablas con JSON: `walk_forward_ablation_predictions`, `walk_forward_ablation_metrics`, `walk_forward_ablation_coefficients` y `walk_forward_ablation_comparison`. Todas identifican `removed_feature` y `subset_model`. Las predicciones conservan también las probabilidades publicadas de M0/M1/M2. Con la muestra actual hay 2430 filas de predicciones (810 por variante), 246 métricas, 1200 coeficientes (intercepto y cuatro columnas por ajuste) y 246 comparaciones. Repetir un ejemplo en tres variantes no aumenta la información independiente.

El historial compartido registra cada retirada antes de su ajuste, con su intento, referencia, columnas y parámetros; al terminar conserva resultado o fallo. Cada una cuenta como una configuración adicional por regla: tres en total, no 240. Si el recorrido falla, solo se registran las variantes que efectivamente empezaron y no se devuelve una familia parcial para publicar. El informe de la familia vincula los intentos y no constituye una cuarta configuración.

Estas tablas dependen de M0/M1/M2 y de sus entradas. Republicar una referencia retira la familia; M3 no es una entrada y republicarlo la conserva. Calcular las retiradas no modifica ninguna tabla de M0/M1/M2/M3. El estado es `diagnostic_only_no_automatic_selection_or_regime_acceptance`. Este incremento no ejecuta sombras, CPCV equivalente, selección automática, SHAP o simulación económica.

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

## Ejecución de la ampliación M3

Se ejecutó el notebook completo en un proceso limpio y sin descargas. Los ochenta ajustes de M3 completaron el recorrido. Las nueve tablas anteriores de M0/M1/M2 y todas las transformaciones causales originales se reprodujeron exactamente. Se guardaron 810 predicciones emparejadas, 82 métricas de M3, 560 coeficientes y 164 comparaciones, con sus JSON. Los otros 65 archivos anteriores comprobados permanecieron intactos.

| Regla | AUC M1 | AUC M2 | AUC M3 | Log-loss M3 | Años M3 mejora a M1 | Años M3 mejora a M2 |
|---|---:|---:|---:|---:|---|---|
| Momentum | 0,595625 | 0,594764 | 0,601982 | 0,669766 | 11 / 40 | 7 / 40 |
| Reversión | 0,630296 | 0,635839 | 0,633992 | 0,644313 | 15 / 40 | 9 / 40 |

En momentum M3 mejora el AUC reunido frente a ambas referencias y la log-loss frente a M2, pero su log-loss sigue siendo ligeramente mayor que la de M1 (0,669000). En reversión mejora AUC y log-loss frente a M1; frente a M2 reduce ligeramente la log-loss, pero empeora AUC. La mejora reunida de AUC no equivale a una mejora en la mayoría de años.

Ninguna de las cuatro comparaciones alcanza los veintiún años favorables fijados. La interacción no queda aceptada con estos resultados; permanecen pendientes los contrastes y la utilidad económica previstos. No se han cambiado la fórmula, la escala, la muestra ni los criterios después de observar M3. La convención de historia recortada cero se decidió con datos de cobertura antes del ajuste real, sin utilizar sus métricas.

Se reconstruyeron las probabilidades con los coeficientes guardados, con diferencia exactamente cero. Las AUC anuales y reunidas se contrastaron mediante pares de etiquetas y las log-loss con su fórmula directa. Las tablas publicadas coinciden exactamente con las calculadas y el notebook queda sin salidas ni contadores de ejecución.

Pasan las 67 pruebas del proyecto. Se añadió una comprobación de la fórmula y causalidad de la interacción y se amplió el recorrido existente para cubrir sus referencias, resultados e invalidaciones. Las dos advertencias de gráficos no interactivos del 09 son las anteriores.

## Ejecución de las retiradas individuales

Se ejecutó el notebook ampliado completo, con datos locales y descargas bloqueadas. Convergieron los 240 ajustes adicionales. Se guardaron 2430 predicciones emparejadas, 246 métricas, 1200 coeficientes y 246 comparaciones, con sus JSON. Las trece tablas anteriores de M0/M1/M2/M3 se reprodujeron exactamente y los otros 65 archivos anteriores comprobados permanecieron intactos. El historial registró las tres retiradas por separado, además de las repeticiones de M1/M2/M3 del recorrido completo.

| Variable conservada | Contribución AUC momentum | Contribución AUC reversión | Contribución log-loss momentum | Contribución log-loss reversión |
|---|---:|---:|---:|---:|
| Volatilidad | +0,000636 | +0,001866 | −0,002694 | −0,000584 |
| Retorno de 24 meses | +0,009088 | +0,012916 | +0,002993 | +0,002116 |
| Drawdown | −0,005236 | −0,005021 | −0,004073 | −0,000720 |

El retorno de 24 meses aporta la mayor contribución de las tres en estas comparaciones reunidas. Conservar volatilidad mejora ligeramente AUC, pero empeora log-loss. Retirar drawdown mejora ambas métricas frente a M2 completo: las AUC sin esa variable son 0,600000 en momentum y 0,640860 en reversión. Estos resultados se limitan a esta logística y a las demás variables incluidas; no se declara una selección definitiva ni una importancia intrínseca de cada característica.

Los años con contribución positiva de AUC son 9/40 y 8/40 para volatilidad, 12/40 y 17/40 para retorno de 24 meses, y 11/40 y 10/40 para drawdown, respectivamente para momentum y reversión. Ninguno alcanza los veintiún años. Los estados no estimables permanecen: ocho años de momentum y uno de reversión. El AUC reunido compara también ejemplos de años distintos y no promedia los anuales; por ello el signo global puede diferir del balance de años positivos y negativos.

Se mantuvieron las variantes y criterios fijados antes de calcular estas retiradas. No se ha eliminado drawdown ni se ha adoptado automáticamente el subconjunto que obtiene mejores métricas. Cualquier elección posterior usará selección interna y evaluación separada, considerando también comparaciones con las referencias, sombras y utilidad económica.

Se reconstruyeron las probabilidades con sus coeficientes, con diferencia exactamente cero. Las AUC se comprobaron con comparaciones entre pares y las log-loss con su fórmula directa, verificando asimismo el signo de las contribuciones. Las tablas publicadas coinciden exactamente con las calculadas. Pasan las 68 pruebas del proyecto, con las dos advertencias gráficas anteriores; se añadió una comprobación de retirada efectiva y signo y se amplió el recorrido existente. El notebook se conserva sin salidas ni contadores.

## Robustez CPCV equivalente

La sección 16–18 del notebook 14 añade las comparaciones CPCV de los seis candidatos fijados. Su [protocolo específico](cpcv_regimen.md) conserva las quince particiones del 10, la muestra común y los mismos parámetros. El resumen principal cubre todo el desarrollo utilizable; el adicional usa las mismas medias de probabilidad en 1950–1989 para alinear meses con walk-forward, sin nuevos ajustes. La comparación no es evidencia independiente ni acepta automáticamente los regímenes. Las salidas y el historial CPCV son independientes de las tablas walk-forward.

## Evaluación económica con las predicciones cronológicas

La sección 19–22 del notebook 14 usa las probabilidades M0–M3 ya publicadas para aceptar señales únicamente si superan 0,5. Su [protocolo económico](evaluacion_economica.md) mantiene cuentas continuas de 1950–1989, con iguales costes e inicio para los filtros y sus referencias. No recalcula modelos, no utiliza medias CPCV ni retornos aislados como una curva, y no anula los criterios de estabilidad incumplidos. Publica cuatro tablas económicas y su historial, sin modificar los experimentos anteriores.

## Ampliación a random forest

Las secciones 23–25 del 14 ajustan el [bosque de complejidad acotada](random_forest.md), manteniendo calendario y muestra. Las comparaciones RF_M1/RF_M2/RF_M3 distinguen la familia de modelo y las variables añadidas. Los controles de la logística no validan esta nueva familia; sus tablas e historial permanecen intactos y las comprobaciones del bosque se registran por separado.
