# Incertidumbre del Sharpe y series para DSR y PBO

Las secciones 44–46 del notebook 14 usan las cuentas netas guardadas en 19–22 y, si está disponible, la cuenta de reversión con el bosque de 40–41. Cada cuenta debe cubrir los mismos 480 meses de enero de 1950 a diciembre de 1989 y compartir los retornos mensuales del efectivo. Los resultados se muestran en el notebook. Se conserva el periodo desde 1990 para la evaluación final autorizada.

## Contraste fijado

Se compara la logística M1 de momentum con la regla original, el veto bajista y el ajuste por volatilidad. Se mantiene la política de ejecución de las cuentas guardadas. El Sharpe anualizado usa la media del retorno neto mensual en exceso del efectivo y su desviación típica muestral. La diferencia es el Sharpe de M1 menos el de su comparador.

Se adapta el bootstrap circular studentizado de Ledoit y Wolf. Cada réplica toma 40 bloques de 12 meses con reemplazo y usa el mismo índice temporal para las dos cuentas. La longitud se fija en un año antes del cálculo. Se usan 5.000 réplicas y semilla 42. El error estándar observado usa la contribución por mes de la diferencia de Sharpe y una estimación HAC de Bartlett con 11 retardos. Cada réplica estima su error estándar a partir de las sumas de esas contribuciones en sus propios bloques. La calibración de la longitud por simulación y el estimador espectral preblanqueado que proponen los autores se sustituyen por esas decisiones para este ejercicio mensual. Se muestran intervalos bilaterales del 95 % obtenidos con el estadístico studentizado absoluto y valores p bilaterales por comparación. [Ledoit y Wolf, apartado 3.2.2](https://www.econ.uzh.ch/apps/workingpapers/wp/iewwp320.pdf)

El diagnóstico por décadas usa tramos fijos de 120 meses y segmenta las cuentas continuas. Conserva cargos, posiciones y liquidación originales. Sirve para describir dónde aparece la diferencia.

## Resultados con las series actuales

| Comparador | Diferencia de Sharpe | IC del 95 % | Valor p |
|---|---:|---:|---:|
| Momentum original | +0,157 | [−0,278, +0,593] | 0,267 |
| Veto bajista | +0,160 | [−0,293, +0,613] | 0,273 |
| Ajuste por volatilidad | +0,158 | [−0,192, +0,509] | 0,219 |

M1 obtiene un Sharpe descriptivo mayor en la cuenta completa. Los tres intervalos incluyen cero. En los años cincuenta M1 queda ligeramente por debajo de los tres comparadores. En cada una de las tres décadas siguientes queda por encima, con la mayor diferencia en los ochenta.

## Cuándo se acumula la ventaja de M1

La sección 52 del notebook 14 usa los capitales al final de cada mes de las cuentas guardadas en 19–22. Traza $\log(V_{\mathrm{M1},t}) - \log(V_{\mathrm{referencia},t})$ frente al momentum original, el veto bajista y el ajuste por volatilidad. La brecha empieza en cero porque las cuentas parten del mismo capital. Su variación mensual mide cuánto terreno ganó o perdió M1 frente al comparador en ese mes. Se conservan las posiciones, los costes y la liquidación de las cuentas originales.

| Comparador | Brecha final | Aporte de octubre y noviembre de 1987 | Aporte del resto de los meses | Porcentaje de la brecha final aportado por esos dos meses |
|---|---:|---:|---:|---:|
| Momentum original | 0,2810 | 0,2659 | 0,0151 | 94,6 % |
| Veto bajista | 0,3627 | 0,2659 | 0,0968 | 73,3 % |
| Ajuste por volatilidad | 0,3576 | 0,2182 | 0,1394 | 61,0 % |

En octubre y noviembre de 1987, M1 quedó en efectivo y los tres comparadores mantuvieron exposición. El ajuste por volatilidad redujo su exposición en noviembre. Esos dos meses, identificados al inspeccionar las curvas, explican gran parte de la ventaja acumulada de M1, sobre todo frente al momentum original. Su aporte se mide en unidades logarítmicas y los 480 meses permanecen en la comparación principal. Se trata de un diagnóstico descriptivo que complementa el contraste de Sharpe. Los capitales proceden de una simulación con precios medios mensuales.

## Inventario de variantes

El inventario recoge los identificadores registrados por regla en el desarrollo y reúne sus intentos. Cada serie publicada se enlaza con el intento de predicción de la logística o con el lote del bosque. Las repeticiones con la misma variante, las comprobaciones CPCV de candidatos cronológicos, los años de reajuste y las sombras aportan resultados a sus respectivas pruebas sin aumentar el número de identificadores de candidatos. M0 y los comparadores fijos siguen en las cuentas como referencias.

| Estado antes de construir la matriz común | Momentum | Reversión |
|---|---:|---:|
| Cuenta neta disponible | 3 | 4 |
| Recorrido cronológico registrado, cuenta pendiente | 9 | 8 |
| Comparación por bloques, reproducir predicciones y simular | 4 | 4 |
| Predicciones CPCV, preparar recorrido cronológico si se incluye | 2 | 2 |

La logística inicial con diez entradas y el último escalón por bloques comparten la especificación de variables e hiperparámetros, evaluada bajo dos diseños temporales. El inventario conserva ambos orígenes. El registro contiene 36 combinaciones de identificador y regla. Las secciones 47–48 construyen la matriz de series a partir del conjunto fijado para la selección económica. [Matriz común de retornos](series_dsr_pbo.md)
