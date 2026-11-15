# Selección interna mediante Clustered MDA

Protocolo del notebook 13 fijado antes de ejecutar esta variante. Se conocen los resultados de la logística con diez características y sus sombras (11/12). Este incremento es una nueva variante de selección dentro del desarrollo 1927–1989; la comparación exterior no representa la evaluación cronológica desde 1990.

## Separación de datos

Se conservan las quince particiones exteriores del 10, con sus mismos ejemplos y exclusiones. En cada entrenamiento exterior se reserva para validación interna el último de los cuatro bloques originales disponibles. Los tres anteriores se utilizan para agrupar y ajustar la logística interna. Es una división interna única y fija, no una validación cruzada interna de cuatro particiones.

El bloque interno se define sobre sus 126 meses originales. Se intersecta con los meses de entrenamiento exterior, manteniendo todas sus exclusiones, y se aplica purga de un mes antes y después y embargo de seis meses después del intervalo interno. El primer mes de embargo coincide con la purga posterior. Las fronteras y distancias se calculan antes de retirar meses sin señal o con calentamiento. Los datos exteriores reservados nunca entran en el entrenamiento, la agrupación o la selección internos.

Con las tablas actuales hay 155–248 ejemplos internos de entrenamiento y 58–93 de validación para momentum; 317–371 y 118–126 para reversión. Todas las divisiones tienen ambas clases. Los recuentos se comprobaron sin entrenar modelos ni probar otras fronteras. Los bloques internos de validación son los originales 4, 5 o 6 según la partición exterior. Esta elección mantiene sencilla la selección, pero hace que dependa de un único periodo interno; se describirá su estabilidad entre particiones exteriores.

## Agrupación fija

Para cada regla y partición se calculan correlaciones de Spearman entre las diez características transformadas, usando exclusivamente los ejemplos internos de entrenamiento con señal. Se utiliza la disimilitud `1 - abs(correlación)` y agrupación jerárquica de enlace completo, con corte 0,30, equivalente al umbral de correlación absoluta 0,70. El enlace completo agrupa según la mayor disimilitud entre miembros. La política se fija antes de calcular las importancias, sin buscar después otros cortes.

La agrupación permite incluir relaciones positivas o negativas sin cambiar el signo ni crear compuestos de las variables originales. Las columnas constantes en el entrenamiento interno se identifican como tales y no se les atribuyen correlaciones estimadas o una importancia medida. Se excluyen de los predictores elegibles. No se rellenan correlaciones no estimables para forzar grupos. La correlación de rangos solo recoge asociaciones monótonas; no garantiza detectar toda redundancia no lineal. Esta agrupación sencilla es una adaptación del TFM, no una réplica del algoritmo completo de agrupación de López de Prado.

Los grupos se fijan con esos datos internos y se conservan al seleccionar y reajustar. Sus identificadores solo tienen significado dentro de su regla y partición. No se promedian importancias de grupos distintos por compartir un número de identificador.

## Importancia y selección

Se ajusta la logística L2 con C=1 sobre los predictores elegibles internos, sin ponderación de clases ni nuevo escalado. Se registra su log-loss y la del ingenuo en validación interna. Para cada grupo se hacen treinta permutaciones de sus filas de validación, usando el mismo orden para todas las columnas del grupo. Los demás predictores y las etiquetas permanecen fijos. No se vuelve a entrenar entre permutaciones.

Se fija la semilla base 42 y se deriva un generador por partición y regla mediante `SeedSequence([42, partición, índice_de_regla])`, con momentum=0 y reversión=1. Las mismas treinta permutaciones se reutilizan para todos los grupos de esa combinación, sin escoger semillas según los resultados. Cada importancia es `log_loss_permutada - log_loss_original`; se conserva el grupo entero si su media es estrictamente positiva. Se muestran también desviación típica y número de repeticiones positivas como descripciones de variabilidad, sin valores p ni otro filtro estadístico.

La permutación de filas mide dependencia del modelo ya ajustado respecto al grupo. No conserva la autocorrelación temporal y no se presenta como un contraste temporal exacto. Cumple una función distinta de las referencias circulares del 12. Un grupo poco importante para esta logística podría ser útil para random forest o boosting; las diez variables se mantienen como candidatas maestras para esos modelos.

Si ningún grupo tiene importancia media positiva, el ajuste exterior conserva solo el intercepto y predice la frecuencia positiva del entrenamiento exterior. No se rescata el grupo menos malo ni se restablecen las diez variables. Si falta entrenamiento con ambas clases o validación interna utilizable, la selección queda no disponible; no equivale a una selección válida de cero grupos y no se cambia la frontera. Las predicciones correspondientes quedan ausentes y el resumen no omite silenciosamente sus meses.

## Reajuste y evaluación exterior

La logística se reajusta con las columnas seleccionadas y todo el entrenamiento exterior original, recuperando los meses que solo se habían excluido para la separación interna. Se siguen respetando la purga y el embargo exteriores. Los bloques exteriores reservados se usan únicamente para predecir y evaluar. Son hasta sesenta ajustes: uno interno y otro exterior por cada una de las treinta combinaciones de partición y regla. Las treinta permutaciones por grupo solo recalculan predicciones.

Se reutilizan la log-loss, AUC y la media de cinco predicciones por ejemplo de los notebooks anteriores. Se compara con las métricas guardadas del 11, sin entrenar de nuevo su referencia. La frecuencia de selección por variable y la composición de grupos se describen entre las quince particiones; no se usa esa frecuencia para construir retrospectivamente un único conjunto global y volver a evaluar sobre los mismos bloques.

Esta variante puede empeorar la logística de diez características. No se declara mejor por conservar menos columnas ni se cambian los criterios tras ver la comparación. La selección se considera parte del algoritmo candidato, no quince configuraciones elegidas con los resultados exteriores. La comprobación con sombras del 12 pertenece al modelo original de diez características: no se traslada a esta variante. Su estado queda `pending_selected_pipeline_shadows`; un contraste posterior deberá considerar también el paso de selección dentro del recorrido.

## Archivos, resultados y registro

El notebook `13_seleccion_clustered_mda.ipynb` explica las fronteras internas, muestra una agrupación y sus importancias, la frecuencia de selección y la comparación exterior. `src/tfm/clustered_mda.py` contiene los cálculos. Se amplían los helpers de logística para aceptar un subconjunto explícito de sus diez columnas; su comportamiento por defecto conserva los experimentos 11/12. SciPy ya está instalada como dependencia transitiva; se declara ahora también como dependencia directa opcional de modelado por el uso de su agrupación jerárquica. No se incorpora una biblioteca nueva.

Se guardan cinco tablas con sus JSON:

- `mda_feature_groups`: una fila por característica, regla y partición; grupo, miembros, media y desviación de importancia del grupo, repeticiones positivas, selección y estado. Los estadísticos de un grupo se repiten en sus miembros para mantener una tabla plana de 300 filas. No son importancias individuales.
- `mda_logistic_predictions`: predicciones exteriores y referencia ingenua, con las mismas claves de fecha, regla y partición.
- `mda_logistic_monthly`: media de cinco probabilidades por regla y mes, conservando las reglas de disponibilidad del 11.
- `mda_logistic_metrics`: métricas por partición y del resumen mensual, incluidas las particiones vacías.
- `mda_logistic_coefficients`: interceptos y coeficientes efectivamente ajustados. Una característica no seleccionada está ausente de ese ajuste, no se publica como un coeficiente estimado de cero.

Los informes conservan los bloques internos, recuentos, listas de columnas seleccionadas y configuración. Antes de ajustar se registra el intento en `outputs/experiments/clustered_mda_trials.jsonl`, identificado como una variante adicional por regla. Las permutaciones de importancia y las particiones no se cuentan como configuraciones independientes. Se conservan los resultados o el error del intento.

Recalcular una entrada de 01, 02, 07, 08, 10 u 11 retira estas cinco tablas. Recalcular 09 o 12 las conserva, porque no son entradas de la selección. Los resultados e historiales originales de 11/12 no se modifican. El guardado mantiene el patrón de tablas separadas y JSON; si falla su celda, debe repetirse completa.

## Verificación prevista y referencias

Se comprobarán las fronteras internas y la ausencia de dependencia de etiquetas exteriores; la agrupación de variables duplicadas o inversas y la permutación conjunta; el caso sin grupos útiles y el recorrido persistido del notebook. La comprobación de compatibilidad reutilizará las tablas originales para asegurar que los helpers por defecto reproducen sus probabilidades y coeficientes.

Referencias: guía del tutor del 7 de noviembre de 2026, marco común y anexo de redundancia; López de Prado (2018), sección 8.3.2 para MDA, y López de Prado (2020), *Clustered Feature Importance*, para el efecto sustitución y el análisis por grupos. La consulta actual de la presentación se limita a su ficha y resumen, pues SSRN no permitió acceder al PDF. La definición operativa y el agrupamiento concreto se apoyan también en [la documentación de permutación de scikit-learn](https://scikit-learn.org/stable/modules/permutation_importance.html), [su ejemplo de agrupación por correlaciones](https://scikit-learn.org/stable/auto_examples/inspection/plot_permutation_importance_multicollinear.html) y [el enlace completo de SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html). No se copia código externo.

## Ejecución y verificación

Se ejecutó el notebook completo sobre los datos locales en un proceso limpio, bloqueando las descargas. Las treinta combinaciones de partición y regla completaron la selección y el ajuste exterior. Se guardaron 300 filas de grupos, 5760 predicciones exteriores, 1152 resúmenes por regla y mes, 64 métricas y 209 coeficientes incluyendo interceptos. Las tablas guardadas coinciden exactamente con las calculadas y los 48 archivos anteriores de datos e historiales permanecieron intactos.

| Regla | Log-loss con diez | Log-loss con selección | AUC con diez | AUC con selección | Variables conservadas por partición |
|---|---:|---:|---:|---:|---|
| Momentum | 0,678228 | 0,667401 | 0,566145 | 0,583347 | 3–7 |
| Reversión | 0,655320 | 0,656645 | 0,605721 | 0,599462 | 3–9 |

La selección mejora las probabilidades de momentum en este resumen de descubrimiento y empeora ligeramente las de reversión frente al modelo de diez características. No se han ajustado cortes, semillas o fronteras para cambiar este resultado. Ambas variantes siguen pendientes de una evaluación económica; la seleccionada no hereda el contraste con sombras del 12. Las frecuencias por variable no se han convertido en una lista global de predictores.

Pasan las 63 pruebas del proyecto, incluidas las tres nuevas. Se reconstruyeron sin reentrenar las probabilidades de los modelos original y seleccionado a partir de sus coeficientes guardados, con diferencia exactamente cero. Se reconstruyeron también los grupos usando solo el entrenamiento interno y se verificó que todos sus miembros comparten estadísticos y decisión de selección. La referencia ingenua coincide exactamente con la del 11. Se revisaron los cuatro gráficos y el notebook se entrega sin salidas ni contadores de ejecución.
