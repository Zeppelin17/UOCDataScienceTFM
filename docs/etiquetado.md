# Propuesta de etiquetado mensual

Fecha: 7 de noviembre de 2026. Estado: propuesta de diseño para revisar antes de implementar el notebook 08. No se han generado etiquetas históricas ni entrenado modelos.

## Pregunta de aprendizaje

Para cada regla, ¿ejecutar su señal durante el mes objetivo habría producido un resultado neto superior a mantener el mismo capital en efectivo durante ese mes?

El horizonte es un mes calendario. La señal se decide en m y se evalúa con los componentes del mes m+1. Se construirán ejemplos de momentum y reversión por separado. Un resultado positivo absoluto no basta: debe superar la alternativa RF del mismo mes.

La propuesta concreta es evaluar operaciones aisladas: partir de efectivo, abrir la exposición que propone la regla y liquidarla al finalizar el mes. Todas parten del mismo capital normalizado. Así la etiqueta no depende de las decisiones previas de un meta-modelo que todavía no existe. Es una convención de aprendizaje, no la etiqueta de la decisión óptima dentro de cualquier cartera previa.

## Convención contable

Se reutilizará la contabilidad de `simulate_baselines` para una ventana de un solo mes, que ya incluye apertura y liquidación final. No se desarrollará un segundo motor financiero. Los supuestos centrales son los ya fijados:

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

La etiqueta será 1 cuando esa diferencia sea estrictamente positiva y 0 cuando sea negativa o empate, salvo el tratamiento puramente numérico que se documente para errores de coma flotante. No se buscará un margen de rentabilidad adicional usando resultados históricos para mejorar la clasificación.

Los meses en que la regla propone efectivo no son operaciones rechazadas ni aciertos/fallos del filtro. Se conservará el calendario para identificarlos, con etiqueta ausente y motivo `no_trade_signal`, y se excluirán del entrenamiento de esa regla. Una señal ausente, un componente inválido o un dato no disponible tampoco se convertirán en una etiqueta 0.

El resultado de una etiqueta solo estará disponible después de terminar su mes objetivo. No podrá incorporarse al entrenamiento antes de esa fecha. El descubrimiento no utilizará resultados desde 1990.

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

Una alternativa sería utilizar la posición previa para comparar decisiones, pero eso introduce dependencia del estado de la cartera. No se incorpora en esta propuesta para mantener un objetivo único y sencillo. El cribado de variables sobre retornos de la anomalía debe precisar su propia respuesta antes de ejecutarse; no se confundirá automáticamente el retorno aislado de etiquetado con la serie de la estrategia continua.

## Alcance y referencia

Las etiquetas son una aproximación retrospectiva sobre promedios mensuales y dividendos reconstruidos, no operaciones ejecutables ni información conocida al emitir la señal. No se aplicará triple barrera: con observaciones mensuales y horizonte de un mes no hay puntos intermedios para identificar cruces anteriores al vencimiento.

El ejemplo de horizonte fijo y meta-labeling de Jansen aporta la estructura de señal más resultado futuro; nuestra comparación con efectivo y contabilidad neta son decisiones específicas del TFM. La revisión del código de referencia y la entrada bibliográfica preparada están en `docs/referencias_jansen.md`.

Antes de implementar: revisar esta convención, cerrar las hipótesis en función de la respuesta que se contraste y concretar la alineación entre etiquetas, características y particiones. La cifra de filas con características completas no equivale al número de operaciones etiquetables de cada regla.
