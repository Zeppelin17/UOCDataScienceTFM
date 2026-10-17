# Paso 1: revisión inicial de los datos

Fecha: 17/10/2026. Estado: diagnóstico de las tres discrepancias completado; revisión de datos aún abierta. No se ha cambiado código de producción, precios, reglas ni informes anteriores. No se ha utilizado el periodo desde 2021 para evaluar o seleccionar estrategias.

## Actualización posterior del alcance

El estudiante ha indicado seguir los periodos recomendados de la guía: desarrollo 1927–1989 y evaluación desde 1990. Se ha incorporado una preparación mensual independiente de Shiller, con historia previa desde 1926. El protocolo de rentabilidades y ejecución continúa pendiente; la preparación no valida por sí misma un backtest con precios medios. El diagnóstico SPY que sigue se conserva como evidencia del planteamiento anterior. Estado y comandos actuales en [shiller_monthly.md](shiller_monthly.md).

## Qué se estaba comprobando

SPY recibe dividendos de las empresas de su cartera y realiza distribuciones a sus partícipes. El contraste compara importes por participación y fecha exdividendo de Yahoo con el listado oficial de State Street. Nuestra simulación calcula retornos mediante el cierre ajustado de Yahoo; no vuelve a sumar dividendos. Revisar los eventos ayuda a comprender los ajustes, pero no certifica todos los cierres o rendimientos.

## Hechos confirmados

Los tres importes distintos están presentes en el snapshot original de Yahoo, antes de nuestra preparación. El original incluye la columna `Capital Gains`, con cero en todas las sesiones de esta muestra: las diferencias no se explican por haber omitido un importe no nulo de esa columna. La preparación no ha cambiado estos tres dividendos.

| Fecha exdividendo | Yahoo original | State Street total | Tiingo, tabla pública indexada |
|---|---:|---:|---:|
| 17/12/1993 | 0,317000 | 0,287239 | 0,287239 |
| 15/12/1995 | 0,382000 | 0,372000 | 0,372000 |
| 20/12/1996 | 0,367000 | 0,406810 | 0,406810 |

La tabla de [Tiingo](https://app.tiingo.com/spy/dividends) corrobora los totales del emisor. Se consultó mediante la versión indexada del buscador; la página directa no renderizó consistentemente el historial. No se ha descargado ni integrado una serie diaria de Tiingo. La coincidencia de dos publicaciones no demuestra independencia de toda su cadena de proveedores ni identifica por sí sola el origen de un error en Yahoo.

En 1996 el emisor desglosa 0,286810 de renta, 0,08 de ganancias a corto plazo y 0,04 a largo plazo. Yahoo muestra aproximadamente renta más ganancias a corto plazo, pero no se ha demostrado la causa de esa clasificación/omisión. Las causas últimas de 1993 y 1995 tampoco están resueltas. No se afirma que las tres diferencias sean simples errores de redondeo.

## Relación con el cierre ajustado

Yahoo [documenta](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html) un ajuste retrospectivo por dividendo mediante el multiplicador `1 - D/C_anterior`. En el snapshot, la variación del cociente `adjusted_close/close` en esas tres fechas implica repartos de aproximadamente 0,316940; 0,381968 y 0,366990 USD. Son consistentes con los eventos Yahoo hasta el ruido numérico de los precios almacenados, no con los totales del emisor.

Este es un control interno de coherencia y una indicación de que las diferencias afectan al retorno ajustado utilizado. No es una validación externa del cierre ajustado ni una contabilidad exacta de cobros y reinversión.

## Sensibilidad acotada

Se ha calculado un escenario auxiliar: mantener todos los precios y retornos Yahoo y sustituir únicamente los tres multiplicadores de distribución por los correspondientes a los totales del emisor. No se publica como serie corregida ni se modifica ningún dataset.

- Cambio relativo del capital final de comprar y mantener, sin costes, durante toda la muestra: **−0,027104 %**. Es un cambio relativo del capital final, no puntos porcentuales de rentabilidad acumulada.
- Mayor cambio de una rentabilidad mensual: **0,065015 puntos porcentuales**.
- Cambios de signo en las señales mensuales teóricas: **0 de 323** para momentum 12–1 y **0 de 334** para reversión. Se excluye enero de 1993 por ser parcial.

Estos cálculos no evalúan un modelo entrenado, la ejecución de las anomalías, costes o posiciones cortas. Que no cambie el signo de las reglas no implica que tampoco cambien variables, etiquetas o predicciones. No se declara irrelevante el problema para cualquier estudio. La decisión de diciembre de 2020 no autoriza ejecutar ni etiquetar una operación en 2021 durante el desarrollo.

La conclusión proporcionada es que estas tres discrepancias, consideradas aisladamente, no justifican desechar toda la muestra ni prolongar indefinidamente la investigación. Deben conservarse documentadas y revisarse en la sensibilidad final si se mantienen estos datos. Los informes de discrepancias conservan su estado `failed`.

## Contraste de precios: pendiente

No se ha obtenido todavía una segunda serie de cierres comparables. La coincidencia de dividendos no acredita los precios. Los intentos acotados de consultar históricos públicos de Tiingo y Nasdaq no proporcionaron un fichero utilizable. Wall Street Numbers cita Yahoo entre sus fuentes: no se acepta como corroboración independiente de este dataset. Los Excel del emisor con NAV o primas/descuentos tampoco equivalen a cierres de mercado.

La [documentación EOD de Tiingo](https://www.tiingo.com/documentation/end-of-day) ofrece cierre, cierre ajustado y distribuciones, pero requiere un token de acceso. Antes de implementar un adaptador habría que verificar acceso efectivo, cobertura, significado de los ajustes y uso permitido. No se ha dado por contratado ni disponible ese servicio. No se cambia de proveedor como respuesta automática a tres discrepancias.

## Hallazgo de alcance: muestra recomendada en la guía

La guía local actual `Guia TFM ML gestion Inversiones L1 v26-27.pdf`, página 2, recomienda para 1.B descubrimiento en **1927–1989** y prueba fuera de muestra en **1990–2026**, con datos mensuales. La página 4 plantea ampliar historia desde 1926 con Kenneth French o Shiller para disponer de más observaciones. Son recomendaciones; la misma guía también propone SPY como fuente accesible.

La memoria y la configuración actuales utilizan SPY desde 1993 y reservan desde 2021. No pueden replicar literalmente la separación histórica recomendada, pues el ETF no existía antes de 1993. Hay que confirmar si la adaptación está acordada con el tutor antes de fijar la muestra definitiva. No se cambia de forma unilateral ni el periodo reservado ni el instrumento. No se empalman índice y ETF como si fuesen la misma serie. Esta decisión puede ser más importante para la robustez del TFM que las tres diferencias de distribuciones.

## Próxima decisión y criterio de cierre

1. Confirmar el acuerdo sobre instrumento, historia y separación temporal. Si se mantiene SPY, justificar la adaptación y el reducido número de observaciones mensuales. Si se adopta historia larga del índice, planificar expresamente ese cambio y sus fuentes.
2. Elegir una comprobación externa de precios factible, o documentar su ausencia y el alcance que permite la muestra. No llamar a la fuente totalmente validada.
3. Fijar el tratamiento: conservar Yahoo con limitación y sensibilidad documentadas, o producir otra serie versionada si la evidencia y el protocolo lo justifican. La documentación de una discrepancia no la convierte en una comprobación superada.

No se necesita ampliar la CLI para completar el diagnóstico. Un cambio de fuente, muestra o método de ajuste sí requiere un plan de implementación previo. Todavía no se da por cerrado el paso 1 ni se pasa automáticamente al 2.

## Reproducción y evidencia

El diagnóstico puntual queda bajo `outputs/reviews/step1_20261017/`, excluido de Git, con `diagnostic.py` y `diagnostic.json`. Usa la preparación `20261004T091516893454Z_b6728748b4c84cb09428cef28e5d3a49` y la referencia SSGA `20261017T155931699464Z_7a02f214a6d14f39bf604aedef129fd7`, con verificación de huellas de los originales. El JSON registra rutas, huellas, importes, fórmulas y resultados. La prueba puede repetirse con `.venv/bin/python outputs/reviews/step1_20261017/diagnostic.py` desde la raíz; sin argumento solo imprime el resultado y no crea archivos.
