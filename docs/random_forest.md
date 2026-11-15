# Segundo candidato: random forest de complejidad acotada

Protocolo fijado antes del primer ajuste de random forest, tras conocer las métricas predictivas y económicas de la logística. Es una nueva familia prevista con el tutor, no una modificación de la logística para borrar sus resultados desfavorables. Se conserva el desarrollo 1927–1989 y la prueba cronológica 1950–1989. No se consulta el periodo desde 1990.

## Pregunta y candidatos

¿Un conjunto de árboles pequeños capta relaciones que una suma lineal no representa? Se entrenan por separado las dos reglas y tres listas fijas:

| Candidato | Columnas |
|---|---|
| RF_M1 | Retorno mensual y momentum 12–1 |
| RF_M2 | RF_M1 + volatilidad de 12 meses + retorno de 24 meses + drawdown de 12 meses |
| RF_M3 | RF_M2 + mercado bajista × volatilidad, con su transformación causal ya fijada |

Se conservan las mismas columnas transformadas y disponibilidad común que en la logística. Un árbol no necesita z-score para comparar umbrales, pero mantener las entradas permite comparar las familias sin cambiar también la preparación. La winsorización sigue siendo parte del diseño común. No se usan los resultados del cribado para elegir columnas ni se aplica una selección global mediante MDA.

Cada árbol pregunta, por ejemplo, si la volatilidad supera un nivel y después si el retorno anterior es positivo. Esas divisiones se aprenden solo del entrenamiento. El bosque promedia las probabilidades de sus árboles. Ya puede representar interacciones sin añadir el producto de M3; por tanto, RF_M3 frente a RF_M2 mide el valor de incluir esa representación explícita, no la aparición por primera vez de interacciones. No se atribuye un coeficiente aislado o causal a cada columna.

## Parámetros fijados y muestra pequeña

Se fija `RandomForestClassifier` de scikit-learn con 200 árboles, profundidad máxima 3, mínimo 20 observaciones por hoja, mínimo 2 para proponer una división, todas las columnas disponibles para cada división (`max_features=1.0`), criterio Gini, bootstrap del entrenamiento, sin pesos por clase, semilla 42 y un único proceso. Se conservan explícitamente `max_samples=None`, `max_leaf_nodes=None`, `min_impurity_decrease=0.0` y `ccp_alpha=0.0`.

La profundidad limita a ocho hojas por árbol. El mínimo por hoja evita decisiones sobre grupos muy pequeños; los primeros entrenamientos pueden producir menos hojas o solo una. Los 200 árboles estabilizan el promedio, pero no equivalen a 200 observaciones ni configuraciones independientes. Son valores convencionales previos al ajuste, no hiperparámetros óptimos demostrados. No se ejecuta una rejilla, ajuste automático, sobremuestreo o calibración. Si más adelante se buscan parámetros, se hará dentro del entrenamiento con el mismo procedimiento para las listas comparadas.

Se reutilizan la etiqueta central, la muestra de diez características disponibles, el calendario anual de cuarenta pruebas y la purga de diciembre anterior. Cada año entrena con historia hasta noviembre del año anterior. No hay entrenamiento posterior a la prueba; el embargo posterior no es aplicable. La interacción se construye una vez con el pasado de cada fecha antes de filtrar señales. Se conservan exactamente los mismos ejemplos que para la logística, sin eliminar meses para favorecer un candidato.

## Ajuste, comparación y límites

Se calculan ochenta ajustes por lista, 240 en total. Los tres candidatos comparten fechas, parámetros y semilla. Una única clase de entrenamiento deja el bosque no estimable; sus probabilidades quedan ausentes y no se reemplazan por resultados de otro candidato. Las pruebas vacías y de una clase permanecen en las métricas con los estados ya fijados. La falta de predicciones impide una métrica completa; no se recortan observaciones.

Se reutilizan AUC/log-loss por año y reunidas, con una probabilidad por operación cronológica. M0 sigue siendo la frecuencia del entrenamiento anual. Se comprueban las fechas, etiquetas y frecuencias respecto a las referencias publicadas de M0/M1/M2 logísticos, que no se reajustan. La comparación entre familias usa RF_M1 frente a L2_M1 y RF_M2 frente a L2_M2: cada pareja tiene exactamente las mismas columnas. No requiere resultados de M3 logístico ni la evaluación económica; RF_M3 se compara con sus propias referencias RF_M1 y RF_M2.

Los cinco contrastes mantienen los cuarenta años, incluidos los no estimables. Una mejora positiva significa AUC del candidato menos referencia y log-loss de referencia menos candidato. La estabilidad exige veintiún años favorables como descripción del criterio previsto; no se cambia el denominador tras observarlos. Ninguna comparación acepta por sí sola el régimen o acredita utilidad económica. Las sombras de logística no validan random forest.

Este incremento se limita al walk-forward. CPCV equivalente, sombras específicas, Clustered MDA específico del bosque, evaluación económica, DSR/PBO y SHAP quedan pendientes. No se generan importancias Gini como sustituto de Clustered MDA/SHAP ni se elige el ganador automáticamente. EBM seguirá condicionado al estudio de relaciones no lineales; gradient boosting será otro incremento con su protocolo propio.

## Archivos y registro

Las secciones 23–25 del notebook 14 pueden ejecutarse por separado con 01/02/07/08 y M0/M1/M2 logísticos preparados. No necesitan 09–13, CPCV del 14, M3 logístico o sus cuentas económicas. Se reutiliza scikit-learn ya instalado; no hay dependencias nuevas, CLI o configuraciones de entrada.

`src/tfm/forest.py` contiene el recorrido. Se publican cuatro tablas `forest_walk_forward_*`: predicciones (incluyen las referencias originales), métricas de los tres candidatos y M0, diagnóstico de los 240 ajustes y las cinco comparaciones. M0 se muestra una sola vez, sin tratarlo como otro bosque ajustado. No se guardan árboles serializados o coeficientes ficticios.

Cada candidato por regla es una configuración nueva y se registra antes de ajustar en `outputs/experiments/forest_trials.jsonl`, con fin o fallo. Los años y árboles no se cuentan como configuraciones nuevas. Repetir la misma lista y parámetros conserva su identidad, pero no borra intentos ni decisiones ya observados. El registro no determina por sí solo el número efectivo de ensayos del futuro DSR/PBO.

Regenerar datos, características, etiquetas o publicar M0/M1/M2 logísticos retira estas cuatro tablas. Repetir 09–13, CPCV del 14, M3 logístico, las retiradas o las cuentas económicas las conserva: no son entradas del bosque. Publicar el bosque conserva las referencias previas. No se modifica la memoria automáticamente; las referencias bibliográficas ya previstas para árboles/bosques se revisarán al redactar el apartado correspondiente.

## Resultado de la ejecución local

Se han completado los 240 ajustes previstos, con 200 árboles cada uno, profundidad observada no superior a tres y hojas con al menos veinte observaciones distintas del entrenamiento en esta muestra. Se publican 810 predicciones cronológicas, 328 métricas, 240 diagnósticos y 410 comparaciones. Los 120 archivos anteriores de datos y experimentos conservan exactamente su contenido. No se ha reajustado la logística, descargado fuentes o consultado datos desde 1990.

| Modelo | AUC momentum | Log-loss momentum | AUC reversión | Log-loss reversión |
|---|---:|---:|---:|---:|
| M0 | 0,497251 | 0,684939 | 0,416244 | 0,661412 |
| L2_M1 (referencia) | 0,595625 | 0,669000 | 0,630296 | 0,644959 |
| L2_M2 (referencia) | 0,594764 | 0,673069 | 0,635839 | 0,644421 |
| RF_M1 | 0,600430 | 0,684830 | 0,669165 | 0,622724 |
| RF_M2 | 0,598298 | 0,675990 | 0,668063 | 0,626402 |
| RF_M3 | 0,598336 | 0,676924 | 0,663733 | 0,628493 |

Los tres bosques superan la referencia de AUC 0,54 y mejoran la log-loss de M0, aunque la mejora de log-loss de RF_M1 para momentum es muy pequeña (aproximadamente 0,000109). No se declara superada la puerta completa: faltan sus sombras específicas. M0 cambia entre entrenamientos anuales y su AUC reunida no tiene por qué ser 0,5.

Frente a la logística de iguales columnas, el bosque mejora la AUC global de ambas reglas. En momentum empeora la log-loss, lo que muestra que ordenar ligeramente mejor no implica ofrecer mejores probabilidades. En reversión mejora ambas medidas. Sin embargo, esas diferencias reunidas no se reproducen como mejoras de AUC en una mayoría de los cuarenta años.

| Candidato frente a referencia | Años con mejora AUC, momentum | Años con mejora AUC, reversión |
|---|---:|---:|
| RF_M2 frente a RF_M1 | 10/40 | 17/40 |
| RF_M3 frente a RF_M1 | 11/40 | 18/40 |
| RF_M3 frente a RF_M2 | 5/40 | 4/40 |
| RF_M1 frente a L2_M1 | 17/40 | 15/40 |
| RF_M2 frente a L2_M2 | 19/40 | 13/40 |

Hay 32 años con AUC estimable para momentum y 39 para reversión; los restantes se conservan y no cuentan como mejoras. La mayoría sigue siendo veintiuno de cuarenta. La AUC reunida compara también pares de meses de años distintos y no es la media de las AUC anuales: por eso puede mejorar aunque los signos por año no sean mayoritariamente positivos.

Añadir el bloque de régimen o el producto explícito no mejora la AUC reunida frente a RF_M1 en ninguna regla y tampoco cumple la estabilidad requerida. La log-loss de momentum sí mejora al añadir el bloque, pero no sustituye esos requisitos. La diferencia RF_M3 frente a RF_M2 en AUC de momentum es aproximadamente 0,000037, con muchos empates anuales; no se interpreta como prueba de utilidad de la interacción. No se acepta ningún régimen ni se elige otra lista o parámetro para cambiar el resultado.

Se han recalculado AUC y log-loss por año y reunidas con fórmulas independientes, comprobado el signo de las diferencias y contrastado todos los tamaños y fechas de entrenamiento con la purga. Doce reajustes puntuales independientes —tres candidatos, dos reglas y los años 1950/1989— reconstruyen las probabilidades promediando sus árboles, con diferencia exactamente cero. Las tablas guardadas coinciden exactamente con las calculadas y se ha inspeccionado el gráfico.

Pasan las 75 pruebas del proyecto. Permanecen únicamente las dos advertencias previas de visualización no interactiva del notebook 09. El notebook 14 conserva su código compilable sin salidas ni contadores, y la memoria no se ha modificado.
