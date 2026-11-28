# DSR y PBO en el desarrollo

Las secciones 49–51 del notebook 14 usan la matriz de retornos de enero de 1950 a diciembre de 1989. Se aplica el mismo protocolo a momentum y reversión por separado. El universo es el de las 16 variantes cronológicas por regla fijadas en [la matriz de selección](series_dsr_pbo.md). Las cinco referencias sirven para las comparaciones económicas. Cada dato es el retorno mensual después de costes menos el retorno del efectivo del mismo mes. El periodo desde 1990 queda reservado.

## DSR

El Sharpe mensual se calcula como media del exceso dividida por su desviación típica muestral. Calculamos la dispersión muestral de esos 16 Sharpes y la correlación de Pearson media entre las parejas de series mensuales de exceso. Según el apéndice A.3 de Bailey y López de Prado, interpolamos entre una prueba cuando la correlación es uno y 16 pruebas cuando es cero. Usamos `N_efectivo = 1 + (16 − 1) × (1 − correlación)`, acotando la correlación a [0, 1]. La cifra fraccionaria se conserva y se redondea hacia arriba para aplicar la aproximación del máximo normal con un número entero de pruebas. También se muestra la sensibilidad con las 16 pruebas como independientes.

El máximo esperado bajo Sharpe nulo utiliza la dispersión de los Sharpes y la aproximación normal de la ecuación (2). Con una sola prueba su referencia es cero. El DSR aplica el ajuste por asimetría y curtosis ordinaria a la diferencia entre el Sharpe observado y esa referencia, usando los 480 meses. Los cálculos usan unidades mensuales y solo se anualizan los Sharpes de las tablas. El número efectivo es una estimación de la redundancia lineal. El DSR clásico usa el tamaño muestral nominal y conserva sus supuestos sobre la dependencia temporal. El contraste por bloques de Ledoit y Wolf responde por separado a la comparación directa con las referencias. [Bailey y López de Prado, ecuación (2) y apéndice A.3](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)

## PBO

Dividimos los 480 meses en **16 bloques consecutivos de 30 meses** y enumeramos las **12.870** formas de elegir ocho. Cada combinación usa 240 retornos para elegir el filtro con el mayor Sharpe y otros 240 para calcular su rango entre los 16 filtros. Los empates al elegir se resuelven por el orden alfabético del identificador. Los empates de rango reciben el rango promedio. Se guarda el número de combinaciones con empate de selección y de rango exactamente mediano. El rango va de 1, el peor, a 16, el mejor. Se divide por 17 y se aplica el logit. El **PBO** es la fracción de combinaciones cuyo logit es estrictamente negativo, correspondiente a quedar por debajo de la mediana. Los casos exactamente medianos se muestran por separado.

CSCV vuelve a ordenar las cuentas cronológicas guardadas en las dos mitades. Se mantienen sus posiciones y costes ya calculados. Las mitades se reutilizan entre combinaciones, que comparten meses. El PBO mide la fragilidad de seleccionar por Sharpe dentro de este universo histórico. Se acompaña con la fracción de selecciones que tuvieron Sharpe negativo en la mitad complementaria, ya que una buena posición relativa puede coincidir con un Sharpe bajo. [Bailey et al., algoritmo 2.3](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

Los dos controles son diagnósticos del desarrollo. M1 de momentum y el bosque M1 de reversión se señalan por su seguimiento anterior. El análisis incluye también las variantes desfavorables. La elección de la evaluación final se documentará con el resto de la evidencia.

## Resultados de desarrollo

| Regla y filtro de seguimiento | Correlación media | Pruebas estimadas / usadas | Sharpe anualizado | Referencia de Sharpe anualizada | DSR | DSR con 16 pruebas |
|---|---:|---:|---:|---:|---:|---:|
| Momentum, logística M1 | 0,8532 | 3,2013 / 4 | 0,6897 | 0,0480 | 0,999956 | 0,999897 |
| Reversión, bosque M1 | 0,5823 | 7,2652 / 8 | 0,0288 | 0,1874 | 0,158934 | 0,101150 |

| Regla | Ganador por debajo de la mediana | PBO | Ganador con Sharpe negativo en el complemento |
|---|---:|---:|---:|
| Momentum | 7.832 de 12.870 | 60,85 % | 7 de 12.870 (0,05 %) |
| Reversión | 3.225 de 12.870 | 25,06 % | 7.915 de 12.870 (61,50 %) |

En momentum, los filtros tienen Sharpes globales próximos y positivos. M1 tiene alta evidencia respecto al Sharpe nulo ajustado por selección. El PBO muestra que elegir el máximo de Sharpe entre estos filtros suele producir una posición relativa modesta al cambiar de meses, aunque casi siempre se mantiene Sharpe positivo en el complemento. El valor del contraste de Sharpe frente a la regla sin filtrar conserva su propia incertidumbre. En reversión, aunque el ganador conserva mejor su posición relativa, su Sharpe complementario suele ser negativo. El DSR del bosque M1 es bajo.

Se guardan `development_dsr` (32 filas), `development_pbo` (dos) y `development_pbo_splits` (25.740), vinculados al intento de la matriz. Hubo un empate al elegir en reversión y ningún caso exactamente mediano en las dos reglas.
