# Decisiones y limitaciones del estudio

## Alcance actual

Se siguen los periodos recomendados por la guía 1.B: desarrollo mensual **1927–1989** y evaluación desde **1990**, con corte final de 2026 pendiente de fijar. Se conserva historia previa desde diciembre de 1925 para calcular todas las señales de 1927. El código actual prepara el desarrollo, calcula señales y componentes de rentabilidad con RF de French y simula las tres estrategias básicas. La evaluación final, las etiquetas y los modelos permanecen deshabilitados o sin implementar.

Se conservan dos fuentes con funciones diferentes. La serie mensual de Shiller del S&P Composite y sus antecedentes históricos es la base principal para calcular señales y variaciones de precio del estudio; no es SPY ni una serie idéntica al S&P 500 moderno durante todo el periodo. Yahoo Finance aporta observaciones diarias del ETF SPY desde 1993 como fuente auxiliar separada. No se unen ambas series ni se presentan como intercambiables; la simplificación de la herramienta no elimina `yfinance`.

## Significado de los datos

Shiller publica un XLS con muchos campos y fechas. El lector revisa las fechas y selecciona únicamente Date/P/D dentro de la historia previa y el desarrollo; no utiliza los importes desde 1990 ni las columnas con resultados futuros. El original completo se conserva y puede contener esas observaciones excluidas.

- **P:** promedio mensual nominal del índice, en puntos. No es un cierre de mes ni un precio de ejecución.
- **D:** dividendo anualizado e interpolado, en puntos del índice. No es un pago mensual observado ni una variable conocida necesariamente en tiempo real. No se divide por doce para tratarlo como tal pago.
- **Disponibilidad:** el archivo actual reconstruye la historia; no acredita cuándo se conoció cada valor o revisión.

El lector interpreta correctamente las fechas numéricas YYYY.MM: por ejemplo, 1926.1 representa octubre. Comprueba cobertura mensual, duplicados, valores finitos, precios positivos y dividendos no negativos. No rellena huecos ni elimina duplicados para conseguir una tabla aceptable. La configuración habitual produce 769 observaciones: 13 de historia previa y 756 de desarrollo.

Yahoo se solicita con `auto_adjust=false`, `back_adjust=false`, `actions=true`, `repair=false` y el resto de opciones explícitas en `data.py`. Se conservan cierre, cierre ajustado y eventos con sus escalas separadas. La copia en Parquet conserva la respuesta del adaptador; no el contenido HTTP original ni una captura conocida en cada fecha histórica. Las comprobaciones actuales revisan estructura y coherencia de los precios, pero no acreditan el calendario completo ni los ajustes o la exactitud del proveedor.

## Reglas implementadas

Sea `m` el mes de decisión y `P[m]` su promedio mensual nominal de Shiller:

| Regla | Indicador en `m` | Señal para `m+1` |
|---|---|---|
| Momentum 12–1 | `P[m-1] / P[m-12] - 1` | +1 si positivo; 0 en otro caso |
| Reversión de un mes | `P[m] / P[m-1] - 1` | -1 si positivo; +1 si negativo; 0 si cero |

Momentum excluye el mes más reciente y comprende once variaciones mensuales. El caso no positivo se concreta como efectivo (`momentum_non_positive="cash"`); no se afirma que sea la única variante de la literatura. No se ajustan las ventanas para mejorar resultados.

`decision_period` conserva el último mes utilizado y `target_period` el mes posterior. Las señales ausentes por calentamiento permanecen ausentes y no equivalen a efectivo. Solo se publican meses objetivo de 1927–1989: una decisión de diciembre de 1989 dirigida a enero de 1990 queda fuera.

La señal de momentum para enero de 1927 utiliza diciembre de 1925. Con esa historia previa hay 756 meses objetivo y **756 con ambas señales disponibles**, desde enero de 1927. Las comparaciones futuras deberán compartir fechas y contar también el calentamiento de sus variables. Los meses del calendario no equivalen automáticamente a observaciones utilizables o independientes.

## Protocolo de simulación básica

Se utiliza Shiller de forma consistente para calcular señales y variaciones entre precios medios mensuales. Los resultados se interpretan como una aproximación histórica: asignar una señal al mes posterior no convierte esos promedios en precios negociables. La limitación afecta especialmente a las relaciones de corto plazo y se mantiene en etiquetas y reentrenamientos futuros.

La simulación comprende comprar y mantener, momentum y reversión en los mismos 756 meses de 1927–1989. Cada cuenta parte de 100 unidades de capital y de exposición cero. En t se aplica la señal decidida en t−1. Las reglas permanecen fijas; no se añade un filtro ni se usa información del resultado de t para decidir la posición.

El objetivo mensual es q = +1, 0 o −1 sobre el capital después de comisiones. Momentum solo admite +1 y 0; reversión admite los tres estados. Las señales ausentes bloquean el cálculo, sin convertirse en efectivo. Los retornos usados son la variación de precios, el dividendo aproximado opcional y RF, según las fórmulas del apartado siguiente.

**Cuenta mensual.** Sea E el capital antes de negociar, N el nominal firmado arrastrado del mes anterior y c la tarifa por importe negociado. Para no invertir también el dinero destinado a pagar la comisión, se resuelve T = |q·(E−c·T)−N|. Si A = q·E−N y s = signo(A), entonces T = |A|/(1+s·q·c). Se descuenta c·T y el capital restante B = E−c·T determina el nominal q·B. Esto incluye apertura, cambios de dirección y reajustes de los cortos cuando el nominal ha variado respecto al capital.

La contribución de precio es q·B·r_precio. Si se incluyen dividendos, su contribución es q·B·r_dividendo_aproximado. Los largos reinvierten ese dividendo sin comisión separada de reinversión; su nominal al final del mes coincide con su capital. El efectivo recibe B·RF. Un corto recibe B·RF solo sobre el capital aportado; los ingresos de la venta corta no reciben interés adicional. El corto paga B·b/12 de préstamo (b anual), además del dividendo debido. Su nominal al final es −B·(1+r_precio), pues el dividendo se paga con efectivo, y se usa ese nominal para calcular el reajuste del mes siguiente. No se incorporan los ingresos de vender prestado como beneficio.

En diciembre de 1989 se liquidan todas las posiciones y se cobra c sobre el valor absoluto del nominal final. El efectivo no genera un coste de liquidación. Se detiene el cálculo si el capital resulta no positivo o no finito; no se simulan llamadas de margen o cierres forzosos intramensuales, impuestos ni restricciones históricas de disponibilidad de títulos. La exposición es una convención de la aproximación, no una afirmación sobre instrumentos operables desde 1927.

El escenario central configura c = 0,001 (0,10 %), b = 0,01 (1 % anual) y dividendos incluidos. Los escenarios de negociación previstos son 0 %, 0,10 %, 0,25 % y 0,50 %; los de préstamo se documentan más abajo. Cambiar un parámetro exige regenerar la simulación. La ejecución actual calcula un escenario cada vez; no selecciona automáticamente el más favorable ni aplica una búsqueda de modelos.

**Resumen.** Rentabilidad acumulada = capital final/inicial−1; anualizada = (capital final/inicial)^(12/n)−1. Volatilidad anualizada = desviación típica muestral de retornos mensuales netos por raíz de 12. Sharpe = media del exceso mensual neto sobre RF/desviación típica muestral de ese exceso por raíz de 12, sin valor cuando la dispersión es nula. La caída máxima incluye el capital inicial antes del primer mes. La rotación anualizada suma el nominal de entradas, reajustes y cierre dividido por el capital inicial de cada mes, multiplicando por 12/n; es rotación bruta, sin dividir entre dos. Los costes monetarios se expresan en unidades del capital normalizado, no en euros o dólares invertidos realmente.

Los resultados se guardan en `baseline_simulations.parquet` con sus componentes monetarios y resumen JSON. Regenerar cualquiera de sus entradas los invalida. El simulador diario anterior de SPY continúa retirado; no se mezclan sus convenciones con este simulador mensual.

## Componentes de rentabilidad implementados

Se prepara una tabla de 756 meses, enero de 1927 a diciembre de 1989, sin posiciones, resultados de estrategias, financiación ni costes aplicados. Para cada mes t se conserva P[t-1], P[t] y D[t] y se calculan:

- Variación de precio: `P[t] / P[t-1] - 1`.
- Dividendo mensual aproximado en puntos del índice: `D[t] / 12`.
- Rentabilidad por dividendos aproximada: `(D[t] / 12) / P[t-1]`.
- Rentabilidad total aproximada del índice: suma de los dos componentes de rentabilidad anteriores.
- Efectivo: `RF[t] / 100`, porque el CSV mensual de French expresa RF en porcentaje. RF ya es mensual, no se anualiza ni se divide entre doce.

RF se obtiene del ZIP CSV mensual de tres factores de la biblioteca de Kenneth French; no se usan Mkt-RF, SMB, HML ni los retornos anuales. El ZIP original se conserva con su procedencia, pero solo se convierten importes RF de 1927–1989. La preparación exige los mismos meses para ambas fuentes, sin rellenar ni eliminar observaciones. RF es el rendimiento observado del mes y no se incorpora como predictor del mismo mes.

Se conserva D sin alterar en la tabla preparada de Shiller. D/12 aparece únicamente en la tabla derivada y está identificado como aproximación contable. La reconstrucción de dividendos y el uso de precios medios impiden equiparar estos resultados con pagos observados, cotizaciones negociables o una fuente histórica con versiones disponibles en tiempo real. Esta limitación también afectará a etiquetas y reentrenamientos posteriores. La tabla incluye RF como alternativa de efectivo; no se suma al rendimiento del índice.

La opción 6 prepara RF; la 7 prepara los componentes sin descargar. Ambas tablas se consultan desde la opción 3. También se pueden preparar y explicar desde `notebooks/02_componentes_de_rentabilidad.ipynb`. Preparar Shiller invalida señales y componentes; preparar French invalida únicamente los componentes.

Documentación de la fuente: [French, descripción de los factores](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html). La versión descargada reconstruye la historia y no certifica qué versión estaba disponible entonces. Las fuentes pueden tener distintos últimos meses disponibles; el corte final de 2026 sigue pendiente y deshabilitado.

## Escenarios de coste de préstamo acordados

El 24 de octubre de 2026 se acordó considerar tres escenarios anuales para el préstamo de las posiciones cortas: **0,25 %, 1 % y 3 %**. El 1 % será el escenario central hipotético, el 0,25 % un escenario bajo y el 3 % uno de mayor coste. Se aplicarán únicamente mientras exista exposición corta y deberán mantenerse separados de dividendos debidos, negociación y remuneración del efectivo. Se prorratean por mes sobre el nominal inicial de cada posición corta, conforme al protocolo anterior.

La referencia empírica para contextualizar el escenario bajo es Gene D'Avolio (2002), *The market for borrowing stock*, Journal of Financial Economics, 66(2–3), 271–306, DOI [10.1016/S0304-405X(02)00206-4](https://doi.org/10.1016/S0304-405X(02)00206-4). Estudia datos de un intermediario institucional entre abril de 2000 y septiembre de 2001 y encuentra un coste medio ponderado por valor de 25 puntos básicos anuales (0,25 %). No es una tarifa del S&P Composite ni una estimación para 1927–1989.

Los tres valores son **escenarios de simulación**, no costes históricos reconstruidos ni requisitos numéricos de la guía. Una tarifa moderna de un ETF tampoco certifica el coste de una exposición vendedora en toda la historia. La referencia bibliográfica se incorporará a Materiales y métodos cuando se redacten los supuestos; no se añade una nueva serie de mercado ni se cambia Shiller por otro proveedor.

Se comparará la sensibilidad de las conclusiones a estos costes. Cuando proceda, se informará del coste de préstamo a partir del cual desaparece la mejora frente al comparador, sin escoger costes a posteriori para favorecer al filtro ni utilizarlos para reajustar el modelo con la evaluación final. El protocolo central está descrito arriba; los futuros filtros y modelos se evaluarán bajo los mismos supuestos.

## Uso conjunto de CLI y notebooks

El primer cuaderno, `notebooks/01_datos_y_senales.ipynb`, prepara los datos y explica las señales utilizando `tfm.config` y `tfm.data`, las mismas funciones que utiliza la CLI. No contiene un segundo motor de preparación o de estrategias. La celda de preparación puede descargar el XLS si falta el original de trabajo y regenera las tablas mensuales y de señales en las rutas habituales. Los importes desde 1990 siguen excluidos de la preparación y no se evalúan rentabilidades de estrategias.

Los notebooks se utilizarán para comprender, explorar y explicar el análisis; las funciones reutilizables seguirán en `src/tfm` y la CLI permitirá repetir tareas ya definidas. Los cuadernos se guardarán sin resultados incrustados y se verificarán ejecutando sus celdas en orden desde un estado limpio. `ipykernel` se incorpora como dependencia opcional del entorno de trabajo, sin añadir JupyterLab, gráficos ni gestores de experimentos en este incremento.

## Exposición previa y hallazgos de SPY

Antes de adoptar la separación histórica de la guía se descargaron y examinaron datos de SPY de **1993–2020**, se realizaron auditorías y un benchmark descriptivo de comprar y mantener. No se entrenó un meta-modelo. Esa exposición debe declararse: el nuevo bloque desde 1990 no se describirá íntegramente como nunca consultado. La selección futura de variables, filtros e hiperparámetros debe basarse en el desarrollo anterior a 1990 con el procedimiento fijado antes de evaluar.

El contraste previo con el Excel histórico de distribuciones de State Street encontró 110 coincidencias dentro de la tolerancia y tres discrepancias entre 113 eventos:

| Fecha exdividendo | Yahoo original, USD por participación | State Street, total |
|---|---:|---:|
| 17/12/1993 | 0,317000 | 0,287239 |
| 15/12/1995 | 0,382000 | 0,372000 |
| 20/12/1996 | 0,367000 | 0,406810 |

Las diferencias ya estaban en el original Yahoo. `Capital Gains` era cero en la muestra. En 1996 State Street desglosa 0,286810 de renta, 0,08 de ganancias a corto plazo y 0,04 a largo plazo. La tabla pública de [Tiingo](https://app.tiingo.com/spy/dividends), consultada mediante resultados indexados, coincidía con los totales del emisor. Eso no prueba independencia completa entre proveedores ni identifica las causas últimas. No se integró una serie diaria de Tiingo.

La variación del cociente cierre ajustado/cierre de Yahoo en esas fechas era consistente, dentro del ruido numérico, con sus propios eventos y no con los totales de State Street. Se trata de coherencia interna y una indicación de que las discrepancias afectan al ajuste utilizado, no de una certificación externa de retornos o una contabilidad de reinversión.

Se calculó un escenario auxiliar que sustituía únicamente esos tres multiplicadores de distribución, manteniendo el resto de los datos. El cambio relativo del capital final de comprar y mantener sin costes fue **−0,027104 %**, y el mayor cambio de una rentabilidad mensual **0,065015 puntos porcentuales**. No cambiaron los signos de 323 señales teóricas de momentum ni de 334 de reversión; se excluyó enero de 1993 por parcial. No se publicó una serie corregida. Esto no garantiza que otras variables, etiquetas o predicciones permanezcan iguales ni resuelve las diferencias.

El diagnóstico del 17/10/2026 permanece en `outputs/reviews/step1_20261017/`, con su script y JSON. Las carpetas históricas de originales, preparaciones, referencias e informes permanecen intactas. Los informes con discrepancias conservan su estado fallido; la simplificación no los convierte en controles superados. Para reproducir los flujos antiguos debe recuperarse su código correspondiente desde Git; la revisión `55ebf4e` todavía contiene el coordinador y las auditorías anteriores.

No se obtuvo una segunda serie de cierres comparables. Un NAV o una prima/descuento no sustituyen al precio de mercado, y coincidencias de dividendos no acreditan cierres ni ajustes. Las tres discrepancias aisladas no justifican una investigación indefinida; si SPY se utiliza para resultados finales, deberán conservarse la limitación y una sensibilidad adecuada.

## Desarrollo posterior

Después de resolver el protocolo financiero se incorporarán progresivamente variables de entorno, filtros sencillos, etiquetas, validación temporal, modelos y evaluación. Los candidatos previstos son regresión logística regularizada, random forest y gradient boosting de complejidad acotada. En meta-labeling las reglas fijan la dirección; el modelo acepta la señal o permanece fuera.

Se mantendrán las comprobaciones temporales y, cuando proceda, purga y embargo. Clustered MDA precederá a SHAP. El registro científico de configuraciones y pruebas necesarias para DSR/PBO se concretará al desarrollar los experimentos; eliminar registros técnicos de cada preparación no autoriza a omitir alternativas probadas durante la selección de modelos.

## Fuentes ya utilizadas

- Guía local: `Guia TFM ML gestion Inversiones L1 v26-27.pdf`, sublínea 1.B; periodos e historia larga en las páginas 2 y 4 de la versión revisada.
- Shiller: <https://shillerdata.com/>; enlace XLS concreto en `configs/estudio.toml`.
- Yahoo mediante yfinance: <https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html>.
- Emisor de SPY: <https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy>.
- Distribuciones históricas del emisor: <https://www.ssga.com/us/en/intermediary/resources/documents/etf-dividend-distributions>.

No se presume una licencia abierta para redistribuir los datos por utilizar una biblioteca abierta. El repositorio conserva código y documentación; los datasets permanecen excluidos de Git.
