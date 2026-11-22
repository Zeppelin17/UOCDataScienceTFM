# Gradient boosting con M1 y M2

Comparamos gradient boosting con la logística regularizada y random forest para las mismas señales y listas de variables. M1 usa el retorno del último mes y momentum 12–1. M2 añade volatilidad de 12 meses, retorno de 24 meses y distancia al máximo de 12 meses. Cada variante se ajusta por separado en momentum y reversión. La etiqueta indica si la operación de la regla superó al efectivo después de costes.

## Configuración fijada antes de entrenar

Usamos `GradientBoostingClassifier` de scikit-learn con pérdida logística. El modelo empieza con la frecuencia de éxitos del entrenamiento y añade árboles uno tras otro. Cada árbol se ajusta para reducir el error de la predicción acumulada y su aportación se multiplica por la tasa de aprendizaje.

| Parámetro | Valor | Función |
|---|---:|---|
| `n_estimators` | 100 | Fija el número de árboles de la secuencia. |
| `learning_rate` | 0,05 | Modera cuánto cambia la predicción cada árbol. |
| `max_depth` | 2 | Limita cada recorrido del árbol a dos divisiones. |
| `min_samples_leaf` | 20 | Exige al menos veinte ejemplos de entrenamiento por hoja. |
| `subsample` | 1,0 | Usa todos los ejemplos disponibles en cada etapa. |
| `random_state` | 42 | Reproduce las decisiones aleatorias del ajuste. |
| `n_iter_no_change` | `None` | Mantiene las cien etapas fijadas y utiliza el entrenamiento completo. |

El tamaño de los árboles se acota por tratarse de una muestra mensual pequeña. Se mantienen los hiperparámetros en las dos reglas y listas durante toda la prueba. Es una configuración inicial fijada después de revisar los modelos anteriores y antes del primer ajuste de boosting. Los árboles y años son partes del recorrido de una configuración.

## Comparaciones previstas

Se usan las mismas características transformadas, señales y etiquetas que en las secciones anteriores. Los cuarenta años de prueba van de 1950 a 1989. Cada ajuste usa datos hasta noviembre del año anterior. Los años vacíos o con una sola clase conservan su estado y el periodo desde 1990 queda reservado.

- `GB_M1` frente a `L2_M1` y `RF_M1`, y `GB_M2` frente a `L2_M2` y `RF_M2`, comparan el efecto de cambiar de familia con las mismas entradas.
- `GB_M2` frente a `GB_M1` mide la aportación del bloque directo de régimen en boosting.

Se comparan AUC y log-loss reunidas sobre las predicciones cronológicas, y se cuentan los años de mejora, empeoramiento, empate y sin AUC calculable. Se mantiene el criterio descriptivo de los bloques. Para que una comparación tenga respaldo predictivo, deben mejorar las dos métricas reunidas y el AUC debe subir en al menos 21 de los 40 años. El diagnóstico del régimen y de su utilidad económica requiere las comprobaciones posteriores.

## Ejecución

Las secciones 32–34 del notebook 14 usan los datos de 01/02/07/08 y las referencias M0/M1/M2 logísticas y del bosque guardadas. Comparan las claves, etiquetas, probabilidades de referencia y el identificador de la ejecución del bosque antes de entrenar. Publican cuatro tablas `boosting_walk_forward_*` y un registro de los ensayos en `outputs/experiments/boosting_trials.jsonl`. Las salidas dependen de las referencias de logística y bosque. Las probabilidades guardadas permiten reutilizar los ajustes en la evaluación económica.

## Resultados de desarrollo

| Modelo | AUC momentum | Log-loss momentum | AUC reversión | Log-loss reversión |
|---|---:|---:|---:|---:|
| L2_M1 | 0,595625 | 0,669000 | 0,630296 | 0,644959 |
| RF_M1 | 0,600430 | 0,684830 | 0,669165 | 0,622724 |
| GB_M1 | 0,586500 | 0,694403 | 0,654961 | 0,631986 |
| L2_M2 | 0,594764 | 0,673069 | 0,635839 | 0,644421 |
| RF_M2 | 0,598298 | 0,675990 | 0,668063 | 0,626402 |
| GB_M2 | 0,587042 | 0,691233 | 0,657723 | 0,630921 |

En momentum, ambas variantes de boosting quedan por detrás de la logística y el bosque en las dos métricas de sus comparaciones emparejadas. En reversión, las dos variantes mejoran ambas métricas frente a la logística y quedan por detrás del bosque. GB_M2 frente a GB_M1 sube el AUC reunido en 0,000542 en momentum y 0,002762 en reversión, y mejora la log-loss en ambos casos. El AUC anual mejora en 13 y 20 años, respectivamente. Ninguna comparación cumple el criterio conjunto. El resultado corresponde al recorrido predictivo de desarrollo.

Se verificaron 160 ajustes, cien árboles por ajuste y el corte anterior a diciembre de cada año previo. Las cuatro tablas guardadas reproducen 810 predicciones, 574 métricas, 160 diagnósticos y 410 filas de comparación. Las tablas e historiales previos conservaron su contenido.
