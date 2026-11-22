# Evaluación económica del bosque M1 en reversión

El bosque M1 obtuvo el mayor AUC global en reversión entre los modelos comparados con M1. Este diagnóstico pregunta si usar ese filtro con la política ya fijada mejora la cuenta después de costes. El periodo de simulación va de enero de 1950 a diciembre de 1989, con 480 meses. La evaluación desde 1990 requiere autorización expresa de Pol después de actualizar la memoria y realizar las verificaciones que considere necesarias.

Se reutilizan las probabilidades cronológicas guardadas de `RF_M1`. Una señal activa se ejecuta si `p > 0,5`, conservando su dirección larga o corta. Una probabilidad menor o igual lleva la cuenta a efectivo. Las señales sin operación y los meses con posición cero cuentan en la trayectoria. Si falta una probabilidad activa, el cálculo se detiene.

Se reutiliza el motor contable de las secciones 19–22. La cuenta parte de 100, conserva posiciones entre meses cuando procede y liquida al final. Incluye dividendos aproximados, remuneración del efectivo, coste de negociación del 0,10 % sobre el nominal negociado y coste de préstamo del 1 % anual sobre el nominal corto. Se comparan las cuentas guardadas de efectivo, reversión original, veto bajista, escala por volatilidad y logística M1. Todas usan los mismos meses y parámetros. [Protocolo económico común](evaluacion_economica.md)

El objetivo principal se lee en la diferencia de capital final frente al efectivo. El retorno anualizado, Sharpe, caída máxima, rotación, costes y recuento de señales completan la lectura. El resultado es descriptivo del desarrollo y se presenta junto a la estabilidad predictiva observada. El registro vincula la cuenta a las predicciones del bosque y las referencias económicas utilizadas.

## Resultados de desarrollo

| Cuenta | Capital final desde 100 | Retorno anualizado | Caída máxima |
|---|---:|---:|---:|
| Efectivo | 761,01 | 5,20 % | 0,00 % |
| Reversión original | 9,74 | −5,66 % | −90,76 % |
| Reversión con veto bajista | 26,02 | −3,31 % | −75,30 % |
| Reversión con ajuste por volatilidad | 14,96 | −4,64 % | −85,80 % |
| Reversión con logística M1 | 454,06 | 3,86 % | −23,80 % |
| Reversión con RF_M1 | 751,30 | 5,17 % | −22,77 % |

El bosque siguió 151 de las 479 señales activas, 94 largas y 57 cortas, frente a las 43 de la logística M1. La cuenta mejora frente a la regla original y a los otros filtros, y termina 9,71 unidades por debajo del efectivo. Su Sharpe de 0,0288 indica que el exceso mensual medio fue ligeramente positivo respecto al efectivo. El saldo final recoge la capitalización de todos los meses y quedó por debajo, con mayor variación mensual.

Las secciones 40–41 del notebook 14 muestran la curva de capital y guardan tres tablas. `forest_economic_decisions` conserva las 480 decisiones. `forest_economic_simulations` reúne las seis cuentas mensuales. `forest_economic_metrics` resume cada cuenta, incluyendo los meses con posición y la diferencia de capital frente al efectivo. El historial queda en `outputs/experiments/forest_economics_trials.jsonl`. Regenerar el bosque o las referencias económicas retira las tres tablas dependientes.
