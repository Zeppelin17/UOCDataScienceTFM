# Protocolo financiero: propuesta inicial

Estado: primer simulador largo/efectivo y benchmark de comprar y mantener implementados. Las anomalías y sus comparaciones siguen pendientes. Separa lo que pide la guía de las convenciones propuestas para convertirlo en código. Las convenciones deben fijarse antes de comparar estrategias y no seleccionarse por su rendimiento.

## Base y alcance

La sublínea 1.B de `Guia TFM ML gestion Inversiones L1 v26-27.pdf` plantea momentum de serie temporal 12–1, reversión de un mes, rebalanceo mensual y comparación con alternativas sencillas. Propone SPY como réplica invertible del S&P 500. La guía define momentum largo cuando el retorno es positivo, pero no concreta aquí su posición cuando es negativo, ni los precios de ejecución, financiación o costes numéricos.

Usaremos inicialmente los datos diarios de SPY disponibles desde 29/01/1993 hasta 31/12/2020. Son el bloque de desarrollo, no una representación exacta del índice. El periodo desde 2021 permanece reservado; su final sigue pendiente. El flujo de simulación de desarrollo ya bloquea intervalos y preparaciones que superen el límite leído de configs/experiment_base.toml; el flujo de descarga conserva el intervalo de su propia configuración. Los datos posteriores no se descargarán para elegir estas convenciones.

## Secuencia temporal propuesta

1. Construir los cierres mensuales a partir de la última sesión de cada mes completo.
2. Calcular la señal después del cierre de esa sesión, utilizando únicamente información disponible entonces.
3. Ejecutar el cambio de posición al cierre de la siguiente sesión bursátil.
4. Mantener esa posición hasta la siguiente ejecución, salvo cambios que establezca explícitamente una estrategia futura.

Ejemplo: una decisión calculada después del cierre del último día bursátil de enero se ejecuta al cierre del primer día bursátil de febrero. El movimiento entre ambos cierres pertenece a la posición anterior. La nueva posición empieza a ganar o perder desde ese segundo cierre. Es una convención sencilla con retraso deliberado; no se supondrá que puede operarse retroactivamente al precio que acaba de producir la señal.

Las fechas diarias actuales son etiquetas de sesión. Habrá que identificar las sesiones mediante un calendario bursátil para comprobar que realmente tenemos el último cierre del mes y la siguiente sesión. No usar el último registro de una descarga incompleta como si fuera un cierre mensual confirmado. El calendario y su verificación son un requisito previo a las señales mensuales; el primer simulador diario puede probarse con la tabla existente, dejando visible esta limitación.

## Señales propuestas

Sea `P[m]` el cierre ajustado de la última sesión del mes `m`. Esta variable mide una evolución con ajustes del proveedor; no será un precio de orden.

| Regla | Cálculo al terminar el mes m | Exposición propuesta |
|---|---|---|
| Momentum 12–1 | `P[m-1] / P[m-12] - 1` | +1 si positivo; 0 en otro caso |
| Reversión de un mes | `P[m] / P[m-1] - 1` | -1 si positivo; +1 si negativo; 0 si cero |

El momentum utiliza once retornos mensuales dentro de la ventana de doce meses y excluye el más reciente. La propuesta largo/efectivo para momentum concreta una decisión abierta; no debe confundirse con una réplica largo/corto de toda la literatura citada por la guía. Se documentará y contrastará con el tutor antes de considerar definitiva esa réplica. La reversión sí requiere cortos para conservar la dirección indicada en la guía; no se sustituirán sus señales negativas por efectivo sin identificarlo como otra variante.

No se generan señales sin toda la historia necesaria. Se descarta el mes inicial parcial y se comparte una fecha de evaluación común, posterior al calentamiento, para las comparaciones. El benchmark podrá mostrarse en una historia más larga como descripción, pero la comparación principal utilizará las mismas fechas.

El futuro meta-modelo aceptará o rechazará la señal original: no cambiará su dirección ni ajustará su ventana. Las etiquetas, el horizonte y el umbral de aceptación todavía deben definirse; no se fijan con este documento.

## Primer simulador: comprar y mantener

El incremento implementado permite un benchmark diario largo/efectivo, con capital inicial normalizado a 1, exposición objetivo 0 o 1, sin apalancamiento, participaciones fraccionarias y remuneración del efectivo inicialmente cero. La primera entrada se ejecutará después de un cierre disponible, en el siguiente cierre; no se atribuirá una ganancia anterior a la entrada. La última valoración no supondrá automáticamente una liquidación: si se simula una salida final, se registrará su coste por separado.

Para este benchmark se propone una aproximación de rentabilidad total basada en `adjusted_close`: `r[d] = adjusted_close[d] / adjusted_close[d-1] - 1`. Se interpreta como un índice de rentabilidad total del proveedor con reinversión implícita, no como una contabilidad exacta de acciones y pagos en efectivo. No se añadirán dividendos otra vez. Los precios `close` y los eventos se conservan para una futura contabilidad explícita; no se mezclarán escalas de cierre y cierre ajustado.

Con posiciones expresadas como exposición al capital y actualización al cierre: `capital_previo_al_coste = capital_anterior * (1 + posicion_anterior * r[d])`. El rebalanceo ocurre después de ese retorno. Los costes se deducen de ese capital y la posición nueva se aplica al siguiente intervalo. Se registrarán por separado exposición anterior y posterior, retorno bruto, rotación, coste y retorno neto. Para comprar y mantener con exposición 1, mantener la misma posición no implica una nueva compra diaria.

La aproximación de rentabilidad total no se extenderá automáticamente a cortos. Antes de simular reversión deberán definirse dividendos debidos por el corto, préstamo, financiación, garantías y tratamiento de la exposición. Omitirlos puede falsear la comparación.

## Costes propuestos

El motor recibirá un coste proporcional por unidad de exposición negociada. Para el primer benchmark largo/efectivo, la rotación será `abs(posicion_nueva - posicion_anterior)`: entrar de 0 a 1 negocia una unidad, mantener 1 negocia cero y salir a 0 negocia una unidad. El coste será `capital_previo_al_coste * rotacion * tasa_coste`.

Propuesta de escenarios exploratorios: 0, 5 y 10 puntos básicos por operación de una unidad. Un punto básico equivale a 0,01 %; cinco equivalen a 0,05 %. Son supuestos ilustrativos de sensibilidad, no tarifas verificadas de un bróker ni un modelo calibrado de impacto. El escenario cero servirá para comprobar cálculos y separar el efecto de los costes. No se elegirá un escenario porque favorezca al modelo. Antes de presentar resultados económicos definitivos habrá que justificar un escenario principal y revisar costes de cortos, diferencial de precios y deslizamiento.

## Resultados y límites

El primer simulador produce una trayectoria diaria de capital con retorno bruto y neto, costes y rotación. Permitirá comprobar cálculos con ejemplos pequeños. Las métricas comparativas, Sharpe, DSR, PBO y SHAP se incorporarán cuando exista una comparación y una búsqueda de modelos que evaluar; no se interpretará este benchmark como prueba de eficacia del aprendizaje automático.

Pendiente antes de comparar anomalías: calendario completo, contraste de datos, convención definitiva del momentum, costes y financiación de cortos, universo de fechas común, políticas de riesgo y efectivo, etiquetas, filtros de referencia y particiones temporales. La exclusión del periodo final tendrá que imponerse en los flujos que entrenan y seleccionan modelos.

## Orden de los siguientes incrementos

1. Completado: motor largo/efectivo separado de comprar y mantener, costes explícitos, registros y pruebas de cálculo a mano.
2. Calendario bursátil y tabla mensual, con detección de meses incompletos y sesiones ausentes.
3. Señales momentum y reversión, una vez fijada la política de cortos y la convención del momentum.
4. Variables de entorno y filtros sencillos, integrados con el mismo simulador.
5. Etiquetas, validación temporal y primer meta-modelo.

Cada incremento tendrá su comando y una opción de menú cuando su flujo esté disponible. Se mantendrá una pausa antes de cada commit.


## Contrato del benchmark implementado

`simulate_long_cash(prices, target_exposure, cost_bps=...)` recibe una exposición efectiva **después del cierre** por cada sesión. Debe estar alineada con los precios, comenzar en 0 y contener solo 0/1. Aplica primero el retorno a la posición anterior y después el cambio de exposición y su coste. No interpreta señales ni aplica retrasos adicionales. `simulate_buy_and_hold` genera 0 en la primera sesión y 1 desde la segunda; esa función resuelve el retraso del benchmark. La trayectoria bruta evoluciona sin costes y la neta acumula tanto los costes como su efecto sobre los retornos posteriores.

El intervalo de `configs/buy_and_hold.toml` tiene extremos inclusivos y debe estar dentro de la cobertura de la preparación. Se conservan los originales completos, pero el benchmark reinicia capital y posiciones al principio del intervalo elegido. Las comparaciones futuras deberán compartir las fechas efectivas tras el calentamiento de señales; este resultado descriptivo de toda la historia no será una comparación con periodos distintos.

El resumen incluye fecha de decisión y entrada, capital bruto y neto, retorno acumulado, coste monetario, rotación y caída máxima neta. La caída se mide respecto a máximos incluyendo el capital inicial 1. No se compara la suma de costes directamente con la diferencia de retornos acumulados. Con [100, 110, 121], la entrada ocurre al segundo cierre: capital final 1,10 sin coste y 1,09945 con 5 puntos básicos. La subida anterior a la entrada no se atribuye al benchmark.

No se exige aún un calendario externo: se ejecuta en la siguiente observación y se advierte de esta limitación. No se aceptan silenciosamente intervalos fuera de la cobertura, ni preparaciones alteradas, fallidas o que contengan fechas posteriores al desarrollo, aunque se solicite un subintervalo anterior. No se admiten aún otras convenciones de efectivo, liquidación, instrumento o ejecución.
