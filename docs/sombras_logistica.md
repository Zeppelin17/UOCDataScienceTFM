# Sombras de la regresión logística

Protocolo del notebook 12, fijado el 14 de noviembre de 2026. Se conocen ya las métricas iniciales del notebook 11. Las decisiones siguientes se fijan antes de calcular las sombras, sin presentarlas como anteriores al primer modelo.

## Objetivo y alcance

Comparar el primer clasificador L2 con referencias que alteran la coincidencia temporal entre características y etiquetas, manteniendo el resto del experimento. Se evalúa por separado momentum y reversión sobre 1927–1989. No se entrena otra configuración candidata, se seleccionan variables o se accede al periodo desde 1990.

La guía 1.B pide AUC aproximadamente a partir de 0,54, log-loss inferior al ingenuo y mejores resultados que sombras. Concretamos la comparación principal mediante la mejora de log-loss respecto al ingenuo. La AUC de las sombras se muestra como información complementaria. El percentil 95 es un criterio operativo del TFM, coherente con el criterio de sombras del anexo de la guía; no un contraste exacto ni una probabilidad de que el modelo sea verdadero.

## Qué se desplaza

Se reconstruyen las diez características transformadas con las fórmulas causales fijas de 07/10, sin leer resultados del cribado 09. La rotación utiliza los 713 meses consecutivos con las diez transformaciones disponibles, de agosto de 1930 a diciembre de 1989. Se desplazan juntas las diez columnas, con el mismo desplazamiento para ambas reglas. Se conserva su relación contemporánea y el orden interno salvo el empalme circular. No se vuelve a estimar la transformación sobre la serie desplazada.

Las fechas de decisión y objetivo, las etiquetas, las señales, las marcas de disponibilidad y las particiones permanecen en sus posiciones originales. Los meses previos de calentamiento tampoco se convierten en ejemplos. La selección de meses con operación se aplica después de desplazar sobre el calendario completo; desplazar solo los 442 ejemplos de momentum comprimiría los meses en efectivo. Los ejemplos de validación siguen siendo los 442 de momentum y los 710 de reversión, con cinco predicciones cada uno.

Estas referencias son artificiales: algunas características desplazadas proceden de fechas posteriores, el empalme circular no representa una continuidad histórica y los regímenes pueden cambiar. No son estrategias ejecutables o predicciones causales en sus nuevas fechas. Las rotaciones están relacionadas entre sí y no proporcionan 642 observaciones independientes ni un valor p exacto.

## Desplazamientos y entrenamiento

Se fija una distancia circular mínima de 36 meses en cualquiera de los dos sentidos. Para N=713 se utilizan todos los desplazamientos enteros de 36 a 677, ambos incluidos: 642 sombras. No se escogen semillas, desplazamientos favorables o cantidades distintas después de ver los resultados. Si cambia la cobertura de la fuente, el conjunto se obtiene mediante la misma regla y queda descrito en el informe.

Para cada rotación se repite `evaluate_logistic`: quince particiones para cada regla, L2 con C=1, las diez columnas explícitas, los mismos pesos, purga y embargo, y la misma media de cinco probabilidades por ejemplo. Son 19.260 ajustes previstos. Los ajustes usan solo las filas de entrenamiento de cada partición; no se cambian sus fronteras para adaptarlas a la rotación. La referencia ingenua se calcula con las etiquetas originales de entrenamiento y debe coincidir con la del 11.

Se reutilizan las funciones del 11 para evitar una segunda implementación de entrenamiento o métricas. No se vuelve a entrenar el modelo original: sus predicciones, resumen mensual y métricas se leen y se contrastan entre sí y con los ejemplos y particiones actuales. Deben corresponder a la misma configuración, costes, versión del entorno e intento completado. Si faltan o no coinciden, se pide ejecutar el 11. No se utilizan firmas de archivos.

El recorrido es secuencial, con progreso visible. Cada sombra libera sus predicciones y coeficientes después de extraer el resumen; no se guardan millones de predicciones o modelos serializados. No se añaden dependencias, CLI, configuraciones o infraestructura de ejecución.

## Comparación fijada

Para cada regla, `mejora = log_loss_ingenuo - log_loss_logistica`: mayor es mejor. El umbral es el percentil 95 de las 642 mejoras de sombras, con el método de cuantil por orden superior (`higher`), igual que en el cribado. El modelo original debe superarlo estrictamente. El histograma incluye el umbral y la mejora original.

El criterio operativo de capacidad predictiva se cumple si simultáneamente:

1. La AUC original es al menos 0,54.
2. La mejora original de log-loss frente al ingenuo es positiva.
3. Esa mejora supera el percentil 95 de las sombras.

La tabla muestra también el percentil 95 de AUC de las sombras y la posición de la AUC original, sin convertirlo en un requisito adicional. La comparación se realiza por regla, sin atribuir un control conjunto de error del 5 %. Superar este criterio no selecciona variables ni modelos, demuestra causalidad o acredita rentabilidad neta. La estrategia, los demás candidatos, Clustered MDA, SHAP y DSR/PBO siguen pendientes. No se modifican los parámetros a partir del resultado de esta comprobación.

Se exige la lista completa de desplazamientos, con ambas reglas y métricas finitas. Si cualquier sombra queda sin resultado, los umbrales y el criterio operativo se dejan no disponibles para toda la comparación. Se conservan las filas y el diagnóstico sin calcular percentiles a partir del subconjunto favorable o válido. Una excepción de entrenamiento o una interrupción detiene y registra el intento; no se cambian parámetros automáticamente ni se publica una comparación parcial como completa.

## Salidas y registro

- `data/processed/logistic_shadows.parquet`: una fila por desplazamiento y regla (1284 en la cobertura actual), con log-loss, AUC, mejora, recuentos y estado.
- `data/processed/logistic_shadow_comparison.parquet`: dos filas, con métricas originales, umbrales, indicadores y resultado del criterio operativo.
- Los JSON acompañantes describen el calendario, los desplazamientos, el modelo, la agregación, la regla del percentil y las limitaciones.
- `outputs/experiments/logistic_shadow_trials.jsonl`: inicio y resultado o fallo del recorrido, identificado como referencia de sombras de la variante del 11. Las 642 rotaciones se distinguen de configuraciones candidatas para la selección posterior; tampoco equivalen a ensayos independientes para DSR.

Las salidas del 11 y su historial permanecen intactos. Recalcular cualquiera de las tablas del 11 retira las dos tablas del 12. Regenerar las entradas anteriores también las retira. Repetir el cribado 09 las conserva. Los historiales científicos no se eliminan. El guardado sigue el patrón de tablas y JSON del proyecto; si falla la celda de publicación, se repite completa antes de utilizar sus salidas.

## Comprobaciones esenciales

Se verificarán dos aspectos principales: rotación conjunta sobre meses consecutivos, preservación de columnas ajenas al modelo y distancia mínima en ambos sentidos; y un recorrido sintético pequeño que reutilice el entrenamiento real, contraste las métricas y los percentiles, mantenga incompleta una familia con resultados ausentes y compruebe guardado, registro e invalidaciones. Las pruebas reducen el calendario de rotaciones mediante un proveedor simulado; el notebook de entrega siempre utiliza la regla completa, sin opción de reducirla.

## Referencias

Guía del tutor del 7 de noviembre de 2026: anexo de preparación y sombras (p. 17), y sublínea 1.B, puerta de capacidad predictiva (p. 18). El detalle del percentil para log-loss, la enumeración completa de rotaciones y la agregación mensual son decisiones documentadas de este TFM. El entrenamiento y las métricas corresponden a [primer_modelo.md](primer_modelo.md); el CPCV a [plan_validacion_temporal.md](plan_validacion_temporal.md). No se copia código externo ni se añade una metodología bibliográfica distinta.

## Ejecución y verificación

El 14 de noviembre de 2026 se ejecutaron todas las celdas en un proceso limpio con los datos locales, bloqueando las descargas. Se completaron las 642 rotaciones y los 19.260 ajustes previstos. Se guardaron 1284 filas de sombras y dos comparaciones finales, con sus JSON e historial de inicio y terminación. Los 43 archivos anteriores de datos e historial del modelo original permanecieron intactos; las nuevas salidas coinciden exactamente con las tablas calculadas.

| Regla | AUC original | Mejora original de log-loss | Percentil 95 de mejora de sombras | Criterio operativo |
|---|---:|---:|---:|---|
| Momentum | 0,566145 | 0,002676 | −0,003304 | Se cumple |
| Reversión | 0,605721 | 0,005072 | −0,001222 | Se cumple |

Los umbrales negativos indican que incluso el percentil 95 de esas referencias ofrece peor log-loss que el ingenuo. Las dos mejoras originales son positivas y superiores a sus umbrales. La fracción de sombras con mejora estrictamente menor es 0,982866 para momentum y 0,993769 para reversión. Estas fracciones son posiciones descriptivas dentro de las rotaciones, no valores p exactos ni probabilidades de rentabilidad futura.

Ambas reglas cumplen el criterio operativo previamente fijado. La magnitud de mejora en probabilidades es pequeña y todavía debe estudiarse su utilidad económica, su estabilidad y el efecto de la selección de características. No se han modificado parámetros o umbrales a partir de estos resultados ni se ha evaluado desde 1990.

Pasan las 60 pruebas del proyecto, incluidas las dos comprobaciones nuevas. Se contrastaron de forma independiente la enumeración de desplazamientos, los recuentos de ajustes, la mejora de log-loss y los cuantiles por posición en la muestra ordenada. Se inspeccionó el histograma y los notebooks se entregan sin salidas ni contadores de ejecución.
