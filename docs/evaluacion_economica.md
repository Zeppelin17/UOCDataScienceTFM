# Evaluación económica de las predicciones cronológicas

Protocolo fijado antes de calcular estas simulaciones, tras conocer las métricas predictivas de M0–M3 y CPCV. Es una evaluación del desarrollo, no una confirmación independiente ni la prueba final desde 1990. Sigue la guía del 15 de noviembre de 2026, apartado 5, pp. 19–21.

## Pregunta y decisión fijada

¿Ayudan las probabilidades cronológicas a mejorar los resultados de las reglas originales después de costes? Se evalúan todos los candidatos M1, M2 y M3, conservando M0 como referencia de frecuencia histórica. No se escoge el candidato favorable ni se incluyen ahora los subconjuntos de diagnóstico.

Se acepta una señal activa solo si su probabilidad es estrictamente mayor que 0,5. Una probabilidad igual o inferior implica efectivo. Una señal original cero sigue siendo efectivo; no se exige una probabilidad donde el modelo no tenía una operación que evaluar. Una probabilidad ausente para una señal activa detiene el cálculo: no se convierte en rechazo. No se seleccionan umbrales con los resultados reservados, no se recalibran probabilidades y no se cambia el tamaño de una señal aceptada.

El 50 % es una convención de clasificación sencilla. Predice la frecuencia de superar al efectivo según el etiquetado aislado; no considera la magnitud de las ganancias y pérdidas, no garantiza calibración y no es un umbral óptimo de inversión demostrado. Probar otros valores más adelante constituiría otra decisión de selección que necesitaría evaluación interna y registro.

## Muestra y cuentas

Se requieren 01/02/07/08 y los resultados walk-forward de M0/M1, M2 y M3 del notebook 14. No se usan medias CPCV, sombras ni retiradas individuales. Se comprueban la referencia y los intentos de origen, los parámetros y la correspondencia entre las probabilidades publicadas. Se exige una predicción cronológica por señal activa y regla, con su mes objetivo y año de prueba, en enero de 1950–diciembre de 1989.

Todas las cuentas comienzan en efectivo con el mismo capital inicial en enero de 1950 y liquidan al finalizar diciembre de 1989. Se conservan los 480 meses completos, incluidos meses sin señal o rechazados; los años de reentrenamiento no reinician el capital ni fuerzan liquidación. No se recorta una curva iniciada en 1927 ni se capitalizan los retornos aislados del etiquetado.

Se reutiliza `simulate_baselines` con posiciones continuas: señal aceptada conserva la dirección original; rechazo provoca efectivo y, si hay una posición previa, paga el cierre necesario. Se conservan dividendos D/12, RF, préstamo y negociación del etiquetado central actual: capital 100, negociación 0,001 del nominal comprado/vendido, préstamo anual 0,01, dividendos incluidos. Las posiciones consecutivas no pagan una venta y recompra artificial cada mes. Un corto puede necesitar reajustes aun manteniendo su dirección; la cuenta se detiene ante insolvencia.

## Referencias y medidas

Se recalculan con el mismo inicio, final y costes: comprar y mantener, efectivo, momentum y reversión sin filtrar, veto bajista y ajuste por volatilidad para cada regla. La volatilidad usa las 12 variaciones de precio anteriores, objetivo anual 12 % y exposición máxima uno; el veto usa el retorno anterior de 24 meses. Son las fórmulas ya fijadas en 05/06, sin optimización ni combinación. No hace falta ejecutar esos dos notebooks: se reutilizan sus funciones.

En total se conservan dieciséis cuentas: ocho referencias y ocho filtros (M0–M3 por dos reglas). Se muestran capital, retorno total y anualizado, volatilidad, Sharpe, drawdown máximo, rotación y costes de negociación/préstamo. El Sharpe usa exceso mensual sobre RF, desviación típica muestral y anualización por raíz de doce. Una cuenta íntegramente en efectivo tiene exceso cero y Sharpe no estimable, no infinito o una mejora automática.

Las comparaciones económicas muestran diferencias de Sharpe entre cada filtro y su regla sin filtrar, veto y ajuste por volatilidad, además de M2/M3 frente a M1 y M3 frente a M2. Son diferencias descriptivas, no pruebas de significación. Un Sharpe ausente se conserva como no estimable.

La curva económica no utiliza etiquetas como decisiones: solo las señales originales y probabilidades cronológicas guardadas. Las etiquetas sirven para verificar el origen del experimento. La clasificación de una operación aislada no asegura la decisión óptima cuando existe una posición anterior; este recorrido comprueba precisamente el comportamiento de la cuenta continua.

## Alcance y registro

M2 y M3 no alcanzaron la estabilidad anual requerida. Una mejora económica no elimina ese incumplimiento ni acepta regímenes. Permanecen pendientes las sombras específicas que correspondan y los modelos restantes. Este incremento no calcula DSR/PBO, no genera SHAP, no ajusta modelos ni consulta periodos desde 1990.

Se registran los cuatro filtros y la regla de decisión en `outputs/experiments/walk_forward_economics_trials.jsonl`, identificando los intentos predictivos utilizados. Repetir el cálculo no genera otra configuración. El registro no determina automáticamente el número efectivo de ensayos de DSR/PBO; las decisiones y configuraciones anteriores siguen contando al valorar el sobreajuste.

Se publican cuatro tablas con JSON: `walk_forward_economic_decisions`, `walk_forward_economic_simulations`, `walk_forward_economic_metrics` y `walk_forward_economic_comparison`. Las cuentas y el historial anteriores se conservan. Regenerar datos, características, etiquetas o cualquier familia de resultados M0/M1/M2/M3 retira estas cuatro tablas; publicar CPCV, sombras o retiradas individuales las conserva.

La sección 19–22 del notebook 14 puede ejecutarse en un kernel nuevo si están preparadas sus entradas. Sus funciones están en `src/tfm/economics.py`; no se crea otro notebook, motor financiero, dependencia, CLI o fichero de configuración. No se modifica la memoria automáticamente. Se mantienen las referencias existentes para las reglas y sus comparadores; el umbral fijo y esta organización son decisiones de este TFM.

## Resultado de la ejecución local

Se ha ejecutado únicamente la nueva sección con datos locales. No se ha reentrenado, descargado fuentes o consultado datos desde 1990. Las tablas contienen 3.840 decisiones, 7.680 observaciones de cuenta, 16 resúmenes económicos y 30 comparaciones. Los 111 archivos anteriores de datos y experimentos conservan exactamente su contenido.

| Cuenta | Capital final desde 100 | Retorno anualizado | Sharpe neto | Drawdown máximo |
|---|---:|---:|---:|---:|
| Comprar y mantener | 10.652,29 | 12,38 % | 0,6143 | −39,16 % |
| Efectivo | 761,01 | 5,20 % | No estimable | 0,00 % |
| Momentum sin filtro | 4.665,14 | 10,08 % | 0,5322 | −26,04 % |
| Momentum con veto bajista | 4.299,25 | 9,86 % | 0,5294 | −26,04 % |
| Momentum con escala por volatilidad | 4.321,31 | 9,87 % | 0,5313 | −21,79 % |
| Momentum M1 | 6.178,89 | 10,86 % | 0,6897 | −14,02 % |
| Momentum M2 | 6.900,55 | 11,17 % | 0,7345 | −14,02 % |
| Momentum M3 | 7.246,00 | 11,30 % | 0,7538 | −14,02 % |
| Reversión sin filtro | 9,74 | −5,66 % | −0,8417 | −90,76 % |
| Reversión con veto bajista | 26,02 | −3,31 % | −0,7753 | −75,30 % |
| Reversión con escala por volatilidad | 14,96 | −4,64 % | −0,8263 | −85,80 % |
| Reversión M1 | 454,06 | 3,86 % | −0,2740 | −23,80 % |
| Reversión M2 | 489,40 | 4,05 % | −0,2189 | −23,80 % |
| Reversión M3 | 495,13 | 4,08 % | −0,2170 | −23,80 % |

M0 acepta las 331 señales activas de momentum y rechaza las 479 de reversión: sus cuentas coinciden exactamente con momentum sin filtrar y con efectivo, respectivamente. No es una selección realizada usando esos resultados; es lo que producen las frecuencias de entrenamiento con el umbral fijado. M1/M2/M3 aceptan 284/270/274 señales de momentum y 43/47/46 de reversión. Los meses originales sin señal siguen incluidos en las cuentas.

En momentum, M2 y M3 mejoran el Sharpe frente a M1 y a la escala por volatilidad con esta política. Mantienen un retorno anualizado inferior al de comprar y mantener, aunque con menores caídas. En reversión, los filtros reducen el deterioro de la regla original, pero sus retornos quedan por debajo del efectivo y su Sharpe sigue siendo negativo. Una mejora frente a una referencia perdedora no demuestra atractivo económico frente a RF.

Estos resultados no aceptan el régimen: M2 y M3 ya incumplieron la estabilidad predictiva anual exigida. No se cambia el umbral ni se elige otro periodo para eliminar ese incumplimiento. Las diferencias de Sharpe siguen siendo descriptivas, sin prueba de significación ni corrección DSR/PBO. La guía exige conjuntamente las comprobaciones pendientes, no solo una curva favorable.

La revisión contrasta las identidades contables mensuales, la continuidad exacta del capital entre meses y años, el mismo capital inicial y los costes de liquidación únicamente al final del recorrido. El Sharpe, retorno anualizado y drawdown se han recalculado con fórmulas independientes; se ha verificado el signo de todas las diferencias y que las tablas publicadas coinciden exactamente con las calculadas. El gráfico usa escalas verticales distintas para cada regla e incluye efectivo como referencia explícita.

Pasan las 73 pruebas del proyecto, incluidas tres comprobaciones nuevas del umbral, contabilidad, origen de predicciones y recorrido de la sección económica. Permanecen solo las dos advertencias anteriores de visualización no interactiva del notebook 09. El notebook 14 se conserva sin salidas ni contadores, y su código compila; la memoria no se ha modificado.
