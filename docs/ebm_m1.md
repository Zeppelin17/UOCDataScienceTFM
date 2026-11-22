# EBM aditivo con las dos entradas de M1

El diagnóstico del notebook 14 encontró un cambio repetido de pendiente en el retorno del último mes. Probamos si un modelo con una curva por entrada reproduce ese patrón y si mejora la predicción. Se ajusta un `ExplainableBoostingClassifier` por regla y año, con las mismas dos entradas y señales que `L2_M1`, `RF_M1` y `GB_M1`. El modelo suma un intercepto y las dos aportaciones para obtener la puntuación que la sigmoide convierte en probabilidad de superar al efectivo. [InterpretML](https://interpret.ml/docs/ebm.html)

## Configuración fijada antes de evaluar

| Parámetro | Valor | Función |
|---|---|---|
| `interactions` | 0 | Una función para cada entrada. |
| `feature_types`, `max_bins` | Continuas, 16 | Aprender intervalos con los valores del entrenamiento y limitar su número, incluidos los reservados por la biblioteca. |
| `max_leaves`, `min_samples_leaf` | 2 y 20 | Limitar cada paso de boosting a una división con grupos amplios. |
| `max_rounds`, `learning_rate` | 300 y 0,03 | Fijar cuánto dura y cuánto cambia el ajuste en cada paso. |
| `greedy_ratio`, `cyclic_progress`, `smoothing_rounds` | 0, `True`, 0 | Actualizar por turnos las dos entradas durante las rondas fijadas. |
| `validation_size`, `early_stopping_rounds` | 0 y 0 | Ajustar con todo el entrenamiento anterior al año y sin separación aleatoria. |
| `outer_bags`, `inner_bags`, `n_jobs`, `random_state` | 1, 0, 1 y 42 | Un solo ajuste por ventana, en un proceso y con semilla fija. |

Se usa pérdida logística y `interpret-core==0.7.8`, el paquete base de InterpretML. Las tablas y figuras del proyecto ya aportan la visualización. Se fija una configuración de complejidad acotada antes de calcular sus resultados. [Parámetros de ExplainableBoostingClassifier](https://interpret.ml/docs/python/api/ExplainableBoostingClassifier.html)

## Calendario, interpretación y comprobaciones

Se mantienen los cuarenta años de prueba 1950–1989, el entrenamiento expansivo hasta noviembre del año anterior y la purga de diciembre. Las comparaciones usan AUC y log-loss globales y el recuento de mejoras anuales de AUC. El criterio exige las dos mejoras globales y al menos 21 de 40 años de mejora, con empates y ausencias separados. El periodo desde 1990 permanece reservado.

Las curvas de 1959, 1969, 1979 y 1989 muestran la aportación nativa de cada entrada en la escala de la puntuación. Cada intervalo se acompaña del número de señales del entrenamiento que contiene. Los escalones son tramos aprendidos y sus límites pueden variar según el año y la regla. Los valores verticales son aportaciones a sumar al intercepto. Para estudiar el patrón señalado en el diagnóstico anterior se compara además la aportación del retorno mensual en los mismos tres cortes que delimitan los dos tramos centrales.

Se publican las predicciones, métricas, comparaciones y aportaciones de las fechas de diagnóstico. El registro de ensayos distingue el único diseño por regla de los cuarenta reajustes cronológicos. Las curvas explican el comportamiento aprendido y la tabla de prueba evalúa su capacidad predictiva. El análisis económico y la robustez de los candidatos quedan para sus propias comparaciones.

## Resultados de desarrollo

| Modelo | AUC momentum | Log-loss momentum | AUC reversión | Log-loss reversión |
|---|---:|---:|---:|---:|
| L2_M1 | 0,595625 | 0,669000 | 0,630296 | 0,644959 |
| RF_M1 | 0,600430 | 0,684830 | 0,669165 | 0,622724 |
| GB_M1 | 0,586500 | 0,694403 | 0,654961 | 0,631986 |
| EBM_M1 | 0,584424 | 0,685924 | 0,660560 | 0,621395 |

En el tramo de 0,11 a 0,40 del retorno normalizado, la aportación de esa entrada sube entre 0,91 y 1,18 puntos en momentum y baja entre 0,92 y 1,55 en reversión. Se observa el mismo sentido en los cuatro ajustes. El tramo se sostiene en 8 a 23 señales recientes de momentum y en 16 a 27 de reversión. El EBM representa ese cambio con una curva de la entrada por sí sola, bajo la especificación aditiva. Los ajustes comparten historia y el diagnóstico describe los modelos aprendidos.

En momentum, el EBM queda por detrás de logística y bosque en las dos métricas. En reversión, supera a logística y boosting en ambas métricas globales. Frente al bosque, obtiene menor log-loss y menor AUC. El AUC anual mejora en 17 años frente a la logística, 19 frente al bosque y 16 frente a boosting. Ninguna comparación de EBM alcanza el criterio conjunto. Las curvas aportan una explicación del patrón, y la tabla permite valorar la estabilidad de su predicción por separado.

Se completaron 80 reajustes sobre las mismas 810 señales de prueba. Se verificaron 410 métricas, 246 comparaciones, 224 intervalos de las curvas y 64 efectos locales. Las tablas y los historiales de los experimentos anteriores conservaron su contenido.
