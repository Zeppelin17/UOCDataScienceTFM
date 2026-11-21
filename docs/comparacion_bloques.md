# Comparación incremental de características

Este diseño se fija tras revisar el notebook 14 y antes de calcular las métricas de las nuevas listas. Empieza con logística L2, `C=1`, y conserva la muestra común, la preparación causal y los cuarenta años de prueba cronológica de 1950 a 1989. Para cada prueba se amplía el entrenamiento hasta noviembre del año anterior y se mantiene la separación de diciembre. Se reutilizan las predicciones publicadas de M1. Cada lista se ajusta por separado para momentum y reversión.

## Orden de incorporación

| Modelo | Información que se añade al anterior | Variables acumuladas |
|---|---|---:|
| M1 | Referencia con el retorno del último mes y momentum 12–1 | 2 |
| M1 + media | Distancia del precio a su media de 12 meses. Es la única candidata de precio que faltaba fuera del bloque directo de régimen. | 3 |
| M1 + media + crédito | Diferencial Baa–Aaa y su cambio mensual. Se estudian juntos el nivel y el movimiento del diferencial. | 5 |
| M1 + media + crédito + industrias | Amplitud y dispersión de las doce carteras industriales. Ambas describen cómo se distribuye el movimiento del mercado. | 7 |
| Diez variables | Volatilidad de 12 meses, retorno de 24 meses y distancia al máximo de 12 meses. Es el bloque directo de régimen de M2. | 10 |

El orden pasa de una ampliación de los precios a dos fuentes externas y deja al final el bloque directo de régimen ya utilizado. La posición de cada bloque se fija por su significado y fuente. Cada comparación mide su aportación **dadas las variables ya presentes**. Todos los escalones se calculan aunque el anterior empeore. El último usa las mismas diez candidatas del notebook 11 en una prueba cronológica. Los retrasos y las definiciones de las variables se conservan.

## Agrupación por correlación

Para cada año y regla, se calcula Spearman sobre los predictores transformados de las señales utilizables del entrenamiento. El enlace completo exige que todas las parejas del grupo tengan una correlación absoluta de al menos 0,80. Las correlaciones de 0,70 a menos de 0,80 se muestran como cercanas al corte. Se resumen las parejas, conservando el signo, y la frecuencia con que las dos variables forman parte del mismo grupo. Si una variable es constante en un entrenamiento, la observación de correlación queda ausente.

Los grupos correlacionados sirven para interpretar solapamientos en los escalones fijados. Si un grupo cruza bloques, la comparación mide lo que añade el nuevo bloque cuando el anterior ya contiene parte de esa información. La agrupación se recalcula con cada entrenamiento y sus resultados no cambian las listas. El corte 0,70 del Clustered MDA del notebook 13 sigue correspondiendo a su propio protocolo de selección y permutación.

## Lectura y ejecución

Cada salto muestra la diferencia de AUC, la mejora de log-loss y el recuento de años ganados, perdidos, empatados o sin AUC. Se considera respaldo predictivo para estudiar un bloque si mejoran ambas métricas reunidas y el AUC mejora en al menos 21 de los 40 años. Los resultados son exploratorios en desarrollo y la decisión de conservar variables requiere las comprobaciones posteriores previstas. El tramo desde 1990 permanece reservado.

El bloque del notebook 14 se ejecuta con las salidas de 01/02/07/08 y la referencia M0/M1 ya preparadas. Las tablas se generan en memoria. Cada lista nueva se registra en `outputs/experiments/walk_forward_block_trials.jsonl` como una configuración por regla, con las mismas fechas y parámetros del M1 publicado. Los años son repeticiones de cada diseño en ventanas distintas.

## Resultados del recorrido

En reversión, distancia a la media, amplitud industrial y distancia al máximo formaron un mismo grupo en los 40 entrenamientos. Las correlaciones medianas entre las tres parejas fueron 0,892, 0,858 y 0,836. En momentum, distancia a la media y distancia al máximo quedaron juntas en 4 de 40 entrenamientos. En los otros 36 su correlación quedó entre 0,70 y 0,80. La redundancia depende de las fechas en que opera cada regla, porque las correlaciones se estiman sobre sus propias señales activas.

| Bloque añadido | Δ AUC momentum | Mejora log-loss momentum | Años ↑ AUC | Δ AUC reversión | Mejora log-loss reversión | Años ↑ AUC |
|---|---:|---:|---:|---:|---:|---:|
| Distancia a la media | −0,01036 | −0,00254 | 3 | −0,00551 | +0,00192 | 11 |
| Crédito | −0,01077 | −0,00527 | 7 | −0,00222 | −0,00244 | 7 |
| Industrias | +0,00625 | +0,00002 | 13 | +0,00396 | −0,00099 | 18 |
| Régimen de precios | +0,00064 | −0,00878 | 12 | +0,00495 | −0,00079 | 10 |

Ningún escalón alcanzó el criterio conjunto. El bloque industrial mejoró el AUC reunido en las dos reglas, con distinta respuesta en log-loss y menos de 21 mejoras anuales. Las comparaciones conservaron las 331 señales de momentum y las 479 de reversión de M1. Estos resultados describen la aportación en este orden y con logística L2.
