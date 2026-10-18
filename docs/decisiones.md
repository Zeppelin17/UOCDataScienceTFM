# Decisiones y limitaciones del estudio

## Alcance actual

Se siguen los periodos recomendados por la guía 1.B: desarrollo mensual **1927–1989** y evaluación desde **1990**, con corte final de 2026 pendiente de fijar. Inicialmente se conserva 1926 como historia previa. El código actual prepara el desarrollo y calcula señales; la evaluación, las etiquetas y los modelos permanecen deshabilitados o sin implementar.

Se conservan dos fuentes con funciones diferentes. Shiller permite explorar la historia larga del S&P Composite, con sus antecedentes históricos; no es SPY ni una serie idéntica al S&P 500 moderno durante todo el periodo. Yahoo Finance aporta observaciones diarias del ETF SPY desde 1993. No se unen ambas series ni se presentan como intercambiables. Su uso definitivo se concretará con el tutor siguiendo la guía; la simplificación de la herramienta no elimina `yfinance` ni decide esa cuestión.

## Significado de los datos

Shiller publica un XLS con muchos campos y fechas. El lector revisa las fechas y selecciona únicamente Date/P/D dentro de la historia previa y el desarrollo; no utiliza los importes desde 1990 ni las columnas con resultados futuros. El original completo se conserva y puede contener esas observaciones excluidas.

- **P:** promedio mensual nominal del índice, en puntos. No es un cierre de mes ni un precio de ejecución.
- **D:** dividendo anualizado e interpolado, en puntos del índice. No es un pago mensual observado ni una variable conocida necesariamente en tiempo real. No se divide por doce para tratarlo como tal pago.
- **Disponibilidad:** el archivo actual reconstruye la historia; no acredita cuándo se conoció cada valor o revisión.

El lector interpreta correctamente las fechas numéricas YYYY.MM: por ejemplo, 1926.1 representa octubre. Comprueba cobertura mensual, duplicados, valores finitos, precios positivos y dividendos no negativos. No rellena huecos ni elimina duplicados para conseguir una tabla aceptable. La configuración habitual produce 768 observaciones: 12 de historia previa y 756 de desarrollo.

Yahoo se solicita con `auto_adjust=false`, `back_adjust=false`, `actions=true`, `repair=false` y el resto de opciones explícitas en `data.py`. Se conservan cierre, cierre ajustado y eventos con sus escalas separadas. La copia en Parquet conserva la respuesta del adaptador; no el contenido HTTP original ni una captura conocida en cada fecha histórica. Las comprobaciones actuales revisan estructura y coherencia de los precios, pero no acreditan el calendario completo ni los ajustes o la exactitud del proveedor.

## Reglas implementadas

Sea `m` el mes de decisión y `P[m]` su promedio mensual nominal de Shiller:

| Regla | Indicador en `m` | Señal para `m+1` |
|---|---|---|
| Momentum 12–1 | `P[m-1] / P[m-12] - 1` | +1 si positivo; 0 en otro caso |
| Reversión de un mes | `P[m] / P[m-1] - 1` | -1 si positivo; +1 si negativo; 0 si cero |

Momentum excluye el mes más reciente y comprende once variaciones mensuales. El caso no positivo se concreta como efectivo (`momentum_non_positive="cash"`); no se afirma que sea la única variante de la literatura. No se ajustan las ventanas para mejorar resultados.

`decision_period` conserva el último mes utilizado y `target_period` el mes posterior. Las señales ausentes por calentamiento permanecen ausentes y no equivalen a efectivo. Solo se publican meses objetivo de 1927–1989: una decisión de diciembre de 1989 dirigida a enero de 1990 queda fuera.

Con historia desde enero de 1926, el momentum para enero de 1927 necesitaría diciembre de 1925. Hay por tanto 756 meses objetivo y **755 con ambas señales disponibles**, desde febrero de 1927. Las comparaciones futuras deberán compartir fechas y contar también el calentamiento de sus variables. Los meses del calendario no equivalen automáticamente a observaciones utilizables o independientes.

## Decisiones pendientes antes de simular

La principal consulta al tutor se refiere a cómo utilizar Shiller para contrastar el objetivo del TFM. Cocientes entre promedios mensuales no representan por sí solos la rentabilidad de comprar después de decidir: el promedio siguiente incorpora cotizaciones de diferentes días. Asignar una señal al mes posterior no convierte esos promedios en precios negociables. La cuestión afecta especialmente a las relaciones predictivas de corto plazo.

Antes de producir resultados de inversión hay que acordar el alcance de la simulación y definir:

1. La construcción de retornos, distinguiendo promedios y cierres, dividendos interpolados y pagos observados.
2. La relación entre información disponible, decisión, ejecución y resultado posterior.
3. Exposición, remuneración del efectivo, cortos, financiación, dividendos debidos y costes.
4. Qué conclusiones permite una simulación histórica aproximada y cuáles requieren operaciones ejecutables o datos diferentes.

No se elige otro proveedor automáticamente ni se presenta una preparación estructural correcta como resolución del problema económico. El simulador diario anterior, limitado a SPY largo/efectivo, se ha retirado del código actual. Su retirada no constituye una implementación del simulador mensual.

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
