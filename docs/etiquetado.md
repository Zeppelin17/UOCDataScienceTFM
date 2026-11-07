# Etiquetado mensual y sensibilidad

Fecha: 7 de noviembre de 2026. Estado: criterio central y sensibilidad fijados antes del cálculo e implementados en el notebook 08. No se han entrenado modelos ni contrastado la capacidad predictiva de las características.

## Pregunta de aprendizaje

Para cada regla, ¿ejecutar su señal durante el mes objetivo habría producido un resultado neto superior a mantener el mismo capital en efectivo durante ese mes?

El horizonte es un mes calendario. La señal se decide en m y se evalúa con los componentes del mes m+1. Se construirán ejemplos de momentum y reversión por separado. Un resultado positivo absoluto no basta: debe superar la alternativa RF del mismo mes.

La convención acordada evalúa operaciones aisladas: partir de efectivo, abrir la exposición que propone la regla y liquidarla al finalizar el mes. Todas parten del mismo capital normalizado. Así la etiqueta no depende de las decisiones previas de un meta-modelo que todavía no existe. Es una convención de aprendizaje, no la etiqueta de la decisión óptima dentro de cualquier cartera previa.

## Convención contable

Se reutiliza la contabilidad de `simulate_baselines` con `reset_each_month=True`: el mismo motor reinicia el capital y liquida cada mes. Su modo habitual conserva posiciones entre meses y no cambia. No se desarrolla un segundo motor financiero. Los supuestos centrales son los ya fijados:

- Capital inicial normalizado: 100 unidades; el resultado se expresa también como retorno para no depender de esa escala.
- Negociación: 0,001 del nominal efectivamente negociado tanto al abrir como al cerrar. El coste conjunto no se aproxima siempre por 0,002 porque el nominal de cierre puede variar.
- Dividendos: aproximación D/12 de Shiller incluida. Los largos los reciben y reinvierten; los cortos los pagan.
- Préstamo de títulos: 0,01 anual dividido entre doce, solo para cortos y aplicado al nominal inicial.
- Efectivo: RF mensual observado del mes objetivo.
- El capital aportado a un corto recibe RF según la convención actual; los ingresos adicionales de la venta corta no reciben una segunda remuneración.

El presupuesto inicial financia también la comisión de apertura. Para una exposición completa, el capital tras negociar es B = E0/(1+c). Los valores de dividendos y RF del mes objetivo son parte del resultado que se etiqueta, no predictores disponibles al decidir.

## Resultado continuo y etiqueta

Se conservarán el retorno neto de la operación aislada y el retorno RF, además de la diferencia:

`excess_return = isolated_net_return - rf_return`

La etiqueta es 1 si esa diferencia supera `1e-12` en retorno decimal y 0 en caso contrario. La tolerancia está fijada para tratar el ruido de coma flotante como empate; no es un margen económico elegido según resultados. No se buscará un margen de rentabilidad adicional usando resultados históricos para mejorar la clasificación.

Los meses en que la regla propone efectivo no son operaciones rechazadas ni aciertos/fallos del filtro. Se conservará el calendario para identificarlos, con etiqueta ausente y motivo `no_trade_signal`, y se excluirán del entrenamiento de esa regla. Una señal ausente, un componente inválido o un dato no disponible tampoco se convertirán en una etiqueta 0.

El resultado de una etiqueta solo estará disponible después de terminar su mes objetivo. No podrá incorporarse al entrenamiento antes de esa fecha. El descubrimiento no utilizará resultados desde 1990.

## Sensibilidad predefinida al coste de negociación

Además de la etiqueta central se calcula `label_no_transaction_cost`, poniendo a cero solo la tarifa de negociación del etiquetado. Se mantienen dividendos, préstamo y RF. La definición central sigue siendo la principal; no se escogerá la alternativa que mejor funcione en el periodo de evaluación final. Cualquier evaluación de un modelo entrenado con la alternativa seguirá cobrando los costes del simulador completo.

Las dos definiciones se incluyen en el JSON de salida. Son alternativas de etiquetado consideradas; los entrenamientos y sus retornos fuera de muestra se registrarán cuando existan. Describir sus diferencias no equivale a ejecutar dos backtests o demostrar que un modelo predice. El informe distingue cambios sobre todas las señales activas y sobre los ejemplos con características completas.

## Ejemplos ficticios comprobados con el motor actual

Todos utilizan capital 100, RF mensual 0,30 %, dividendo aproximado mensual 0,20 %, negociación 0,10 % por nominal y préstamo anual 1 %. No son resultados extraídos de los datos del desarrollo.

| Señal y variación de precio | Capital al cerrar | Capital en efectivo | Diferencia | Etiqueta |
|---|---:|---:|---:|---:|
| Compra; precio +1,00 % | 100,997802 | 100,300000 | +0,697802 | 1 |
| Compra; precio +0,10 % | 100,099600 | 100,300000 | −0,200400 | 0 |
| Venta corta; precio −1,00 % | 100,816850 | 100,300000 | +0,516850 | 1 |

El segundo caso gana dinero en términos absolutos, pero obtiene menos que el efectivo y por eso recibe etiqueta 0. En la venta corta se han descontado el dividendo debido, el préstamo y la negociación, incorporando la remuneración del capital aportado.

## Diferencia con la evaluación de una estrategia

La simulación del filtro mantendrá la contabilidad existente de posiciones entre meses. Si se acepta otra señal en el mismo sentido, no se forzará una liquidación y reapertura solo porque el etiquetado utilice operaciones aisladas. Se pagará la negociación realmente requerida, incluyendo cambios de dirección y reajustes, y la liquidación final.

Por ello, la etiqueta no garantiza que rechazar una señal sea la mejor decisión considerando una posición previa. Puede rechazar como ejemplo aislado un movimiento pequeño que habría resultado conveniente manteniendo una posición ya abierta. La evaluación económica comprobará si el filtro aporta valor pese a esa diferencia. No se construirán curvas de inversión sumando o capitalizando los retornos aislados como si fueran la estrategia continua.

Una alternativa sería utilizar la posición previa para comparar decisiones, pero eso introduce dependencia del estado de la cartera. No se incorpora en este incremento para mantener un objetivo único y sencillo. El cribado de variables sobre retornos de la anomalía debe precisar su propia respuesta antes de ejecutarse; no se confundirá automáticamente el retorno aislado de etiquetado con la serie de la estrategia continua.

## Alcance y referencia

Las etiquetas son una aproximación retrospectiva sobre promedios mensuales y dividendos reconstruidos, no operaciones ejecutables ni información conocida al emitir la señal. No se aplicará triple barrera: con observaciones mensuales y horizonte de un mes no hay puntos intermedios para identificar cruces anteriores al vencimiento.

El ejemplo de horizonte fijo y meta-labeling de Jansen aporta la estructura de señal más resultado futuro; nuestra comparación con efectivo y contabilidad neta son decisiones específicas del TFM. La revisión del código de referencia y la entrada bibliográfica preparada están en `docs/referencias_jansen.md`.

## Ejecución y datos guardados

El notebook 08 requiere las tablas de 01, 02 y 07. Muestra los supuestos, construye ambas etiquetas sobre las mismas filas, explica un mes por regla y guarda `data/processed/labelled_signals.parquet` con su JSON. No descarga fuentes ni guarda copias CSV. Si la tabla de características conserva el diseño antiguo, exige volver a ejecutar el 07.

Se conservan 756 meses por cada regla: 1512 filas de calendario con las diez características y las cuentas mensuales. `features_ready` indica cobertura de variables; `training_ready` exige también que la señal proponga operar. La cifra de 749 meses con características completas no equivale al número de ejemplos de entrenamiento de cada regla. Los campos de resultados y ambas etiquetas no son predictores: se utilizará exclusivamente `FEATURE_COLUMNS` para ese fin.

Regenerar precios, señales, componentes o características retira el conjunto etiquetado para evitar reutilizarlo con entradas anteriores. Si una operación resulta insolvente bajo los supuestos del motor, el cálculo se detiene; no se elimina esa observación para conservar solo las favorables.

Se han comprobado cuentas manuales, etiquetas ausentes para efectivo, independencia de meses posteriores y el recorrido del notebook. La inspección de cobertura, conteos y sensibilidad de etiquetas se considera parte del diagnóstico del desarrollo, no una validación del modelo. Las hipótesis y el protocolo descriptivo de contrastes y transformaciones quedan definidos en [hipotesis_y_cribado.md](hipotesis_y_cribado.md), antes de calcular relaciones predictivas. Su implementación y el esquema de selección dentro de las particiones siguen pendientes.
