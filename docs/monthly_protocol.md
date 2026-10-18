# Protocolo mensual con Shiller: señales antes de la simulación

Se mantiene la fuente Shiller indicada entre las alternativas de la guía 1.B, con desarrollo 1927–1989 y evaluación desde 1990 aún deshabilitada. No se añade otro proveedor. El flujo `prepare-shiller` conserva los originales y prepara precios medios mensuales y dividendos anualizados/interpolados; la memoria ya describe sus limitaciones.

## Incremento de señales

`build-shiller-signals` lee una preparación seleccionada explícitamente, verifica su integridad y genera las señales de ambas reglas. Solo utiliza `period` y `price_monthly_mean` para calcularlas. Los dividendos no intervienen en los predictores ni se convierten en pagos mensuales.

Sea `m` el mes que acaba de terminar y `P[m]` su promedio mensual nominal de Shiller:

| Regla | Indicador al terminar `m` | Señal propuesta para `m+1` |
|---|---|---|
| Momentum 12–1 | `P[m-1] / P[m-12] - 1` | +1 si positivo; 0 en otro caso |
| Reversión de un mes | `P[m] / P[m-1] - 1` | -1 si positivo; +1 si negativo; 0 si cero |

La ventana de momentum comprende once variaciones mensuales y excluye el mes más reciente. La configuración declara expresamente `momentum_non_positive = "cash"`. Esta elección largo/efectivo concreta el caso que la guía deja abierto; no se presenta como la única variante de la literatura. No se ajustan las ventanas para mejorar los resultados.

Las señales son un diagnóstico de las reglas sobre la serie disponible, no órdenes ejecutadas ni etiquetas de entrenamiento. Aplicar las reglas a promedios mensuales puede producir señales distintas de las obtenidas con cierres de mes. No se afirma que ambas implementaciones sean equivalentes. La base `monthly_mean_price` se conserva en la configuración, la salida y el resumen.

## Meses y calentamiento

Cada fila distingue `decision_period` (último mes usado para decidir) y `target_period` (mes siguiente). Solo se publican meses objetivo dentro de 1927–1989. Una decisión de diciembre de 1989, dirigida a enero de 1990, no se publica en este flujo.

Los meses sin historia suficiente conservan indicadores y señales ausentes, junto con `both_rules_available = false`. No se sustituyen por una señal de efectivo. Con la preparación predeterminada que empieza en enero de 1926, el momentum para enero de 1927 necesitaría el nivel de diciembre de 1925, que no está presente. Por ello hay 756 meses objetivo y 755 comparables para ambas reglas, desde febrero de 1927. Una preparación explícita con más historia podrá cambiar ese calentamiento sin cambiar las ventanas.

Las comparaciones posteriores deberán compartir los meses en que todas sus variables y señales estén disponibles. Los 756 meses del calendario no equivalen a 756 ejemplos utilizables o independientes.

## Artefactos y reproducción

La configuración independiente está en `configs/shiller_signals.toml`. El menú ofrece selección por número, sin elegir automáticamente la preparación más reciente. No hay descargas durante este flujo.

Cada ejecución conserva configuración, política temporal, manifiesto e informe de la preparación, `signals.parquet`, una copia `signals.csv` para consultar la tabla y `summary.json`. El registro incluye versiones y huellas de los artefactos. Los resultados no sobrescriben preparaciones ni ejecuciones anteriores. Un error de configuración, integridad o cobertura bloquea la generación y se registra; un fallo de publicación elimina salidas parciales.

El tipo del resumen es `shiller_mean_price_signal_diagnostics`. No contiene precios de ejecución, capital, costes, retornos de cartera ni métricas de rentabilidad. El simulador diario de SPY sigue separado y no admite esta tabla mensual.

## Siguiente paso financiero

Antes de simular carteras se concretarán y justificarán:

1. El cálculo de una rentabilidad histórica aproximada con esta fuente, distinguiendo promedios de cierres y dividendos interpolados de pagos observados. No se añadirá `D / 12` como si fuera un pago mensual conocido.
2. La relación entre decisión, ejecución y resultado. Asociar la señal de diciembre a enero no convierte los promedios de esos meses en precios negociables, ni permite atribuir rentabilidades anteriores a la decisión.
3. El efectivo, la financiación de cortos, los dividendos debidos y los costes de negociación. No se extenderá el motor largo/efectivo mediante un simple cambio de signo.
4. Las limitaciones que permitan hablar de una simulación histórica aproximada y las que impedirían afirmar una réplica invertible.

Si las limitaciones impiden contrastar la pregunta de la guía con rigor, se preparará una consulta concreta al tutor antes de cambiar la fuente. Este incremento permite comprobar las señales sin dar por resueltas esas decisiones ni entrenar un meta-modelo. La exposición previa a datos de SPY de 1993–2020 sigue documentada.
