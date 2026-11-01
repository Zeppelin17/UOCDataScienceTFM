# Diagnóstico de fuentes y definición de precios

Revisión del 1 de noviembre de 2026, limitada a importes anteriores a 1990. Resultados reproducidos con `notebooks/00_diagnostico_fuentes.ipynb`. Las verificaciones se ejecutaron con copias temporales, no se regeneraron los datos de trabajo del proyecto.

## Cobertura analizada

| Fuente | Primer mes analizado | Último | Filas mensuales | Meses cubiertos de 1927–1989 |
|---|---|---|---:|---:|
| shiller | 1924-12 | 1989-12 | 781 | 756 |
| industries | 1926-07 | 1989-12 | 762 | 756 |
| BAA | 1919-01 | 1989-12 | 852 | 756 |
| AAA | 1919-01 | 1989-12 | 852 | 756 |
| yahoo | 1927-12 | 1989-12 | 745 | 745 |

La ventana de Shiller incluye 25 observaciones de historia previa y 756 de desarrollo. French contiene retornos mensuales de doce carteras industriales ponderadas por valor desde julio de 1926. Baa y Aaa se conservan como tipos anuales en porcentaje, no como retornos mensuales. El origen o final analizado no representa necesariamente toda la cobertura absoluta de cada fuente.

Yahoo `^GSPC` proporciona diarios desde el 30 de diciembre de 1927 en esta consulta. No cubre enero–noviembre de ese año y no permite sustituir directamente toda la historia de Shiller. Se descarga frecuencia diaria, la disponibilidad de las consultas mensuales puede ser distinta. El último cierre es la última observación disponible de cada mes. Este diagnóstico no certifica todas las sesiones ni el calendario histórico. Se excluye la primera media mensual de Yahoo por su cobertura inicial parcial.

## Contraste en fechas comunes

El panel de precios común comienza en enero de 1928. Tras recalcular ambas reglas con una misma historia inicial y reservar los meses de calentamiento, las señales y sus resultados posteriores comparten **731 meses objetivo, febrero de 1929–diciembre de 1989**. No se mezclan definiciones de precio ni se utilizan resultados desde 1990.

| Serie | Volatilidad anualizada por precio | Correlación con el mes anterior | Media bruta momentum, mensual | Media bruta reversión, mensual |
|---|---:|---:|---:|---:|
| Media de Shiller | 16.998 % | 0.2912 | 0.3444 % | -0.8017 % |
| Media de diarios de Yahoo | 17.058 % | 0.2929 | 0.3477 % | -0.8421 % |
| Último cierre de Yahoo | 20.387 % | 0.1055 | 0.4080 % | -0.2451 % |

La contribución bruta es señal en m multiplicada por variación de precio en m+1, con contribución de precio cero cuando la señal propone efectivo. No incluye dividendos, remuneración RF, préstamo, costes, reinversión ni una cuenta de capital. No debe interpretarse como rendimiento neto ejecutable. La correlación es descriptiva y no constituye un contraste de significación o una demostración de causalidad.

| Comparación | Regla | Señales distintas | Porcentaje sobre 731 meses |
|---|---|---:|---:|
| Media de Shiller / Media de diarios de Yahoo | momentum | 1 | 0.137 % |
| Media de Shiller / Media de diarios de Yahoo | reversal | 8 | 1.094 % |
| Media de Shiller / Último cierre de Yahoo | momentum | 43 | 5.882 % |
| Media de Shiller / Último cierre de Yahoo | reversal | 178 | 24.350 % |
| Media de diarios de Yahoo / Último cierre de Yahoo | momentum | 44 | 6.019 % |
| Media de diarios de Yahoo / Último cierre de Yahoo | reversal | 173 | 23.666 % |

Las dos medias muestran resultados más próximos que cada media frente al cierre. En reversión, Shiller y los cierres de Yahoo discrepan en 178 meses (24,350 %); dentro de Yahoo, media y cierre discrepan en 173 (23,666 %). El efecto de promediar merece tratarse como una cuestión metodológica, además de una limitación de ejecución. Las coincidencias entre proveedores no prueban independencia ni certifican el dato. Los desacuerdos cercanos a cero también pueden depender de precisión o redondeo, no se ha modificado el umbral cero de las reglas para reducirlos.

Una discrepancia puntual adicional aparece en **julio de 1974**: P de Shiller es **79,31**, la media diaria de Yahoo es **82,8191** y su último cierre es **79,309998**. La diferencia entre medias es **−4,237 %**. Se comprobó una vez el XLS publicado el 1 de noviembre de 2026, además del original local y ambos contienen 79,31 para 1974.07. Por tanto, el valor no nace únicamente de nuestra transformación. No se identifica la causa última ni se corrige la serie, la tabla `source_discrepancies.parquet` conserva las cinco mayores diferencias para inspección. Esta coincidencia puntual con un cierre no convierte toda la serie de Shiller en una serie de cierres.

La agregación temporal puede introducir correlación entre variaciones: [Crawley, Reserva Federal (2019)](https://www.federalreserve.gov/econres/feds/in-search-of-lost-time-aggregation.htm), a partir de Working (1960). Este antecedente motiva el contraste, pero no identifica por sí solo la causa de cada diferencia observada. No se escogerá una fuente por su rentabilidad histórica.

## Disponibilidad inicial de características

El diagnóstico comprueba cobertura y calentamiento, no capacidad predictiva. Con un desplazamiento temporal adicional propuesto de un mes para industrias y crédito, nueve características propuestas cubren los 756 meses de desarrollo. La amplitud industrial con media de doce observaciones empieza en agosto de 1927 y quedan **749 meses** con esa característica. No se rellenan los siete meses anteriores. Este cómputo describe la disponibilidad bajo el supuesto, no demuestra las fechas reales de publicación ni que los datos actuales fueran los conocidos entonces.

La dispersión y amplitud son entre industrias, no entre acciones individuales ni ETF. Su universo es más amplio que los componentes del S&P 500. Los índices de riqueza para amplitud deberán construirse con los retornos industriales, conservando ese significado. Se revisará la disponibilidad histórica antes de fijar la tabla final. Los precios reconstruidos, las carteras de French y los tipos actuales de FRED no se consideran automáticamente versiones point-in-time.

VIX y ETF sectoriales no pueden ser predictores aprendidos en 1927–1989. Se mantiene el periodo acordado. El nivel y la variación de Baa–Aaa son candidatos de cobertura larga. No equivalen a un diferencial corporativo frente a Treasury ni a un OAS.

## Decisiones y siguiente paso

- Se conserva Shiller como base principal declarada y el contraste con cierres como análisis separado, sin empalmar series.
- Antes de entrenar se revisará el alcance de las conclusiones sobre reversión, dadas las diferencias de la construcción de precios.
- Se concretarán las características y los rezagos con su documentación; las diez candidatas no son una selección definitiva.
- La CLI y los ficheros de configuración se han retirado. Tanto el diagnóstico como los cuadernos 01–06 se ejecutan directamente.
- No se han entrenado modelos, ajustado ventanas por rendimiento ni realizado la evaluación desde 1990.

## Fuentes

- [Shiller](https://shillerdata.com/).
- [Yahoo Finance: S&P 500](https://finance.yahoo.com/quote/%5EGSPC/history/).
- [French: doce carteras industriales](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_12_ind_port.html).
- [FRED BAA](https://fred.stlouisfed.org/series/BAA) y [FRED AAA](https://fred.stlouisfed.org/series/AAA).
