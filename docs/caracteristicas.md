# Características mensuales del desarrollo

El notebook `07_caracteristicas.ipynb` construye diez características anteriores a cada resultado mensual. No produce etiquetas ni entrena modelos. Requiere Shiller preparado con el notebook 01; lee las doce industrias de French y Baa/Aaa de FRED mediante los mismos lectores del diagnóstico 00, sin descargar Yahoo ni utilizar sus cierres.

## Fechas y unidades

Cada fila representa un mes objetivo t de enero de 1927 a diciembre de 1989. La decisión m es t−1. Los precios utilizados llegan hasta m; industrias y crédito llegan hasta k = m−1 = t−2. El mes extra de retraso de contexto es un supuesto de disponibilidad, no una reconstrucción de las versiones o fechas históricas de publicación. Las medias de Shiller no son cotizaciones negociables.

| Columna | Fórmula en la decisión | Unidad |
|---|---|---|
| `price_return_1m` | P[m] / P[m−1] − 1 | Decimal |
| `momentum_12_1` | P[m−1] / P[m−12] − 1 | Decimal; once variaciones |
| `market_return_24m` | P[m] / P[m−24] − 1 | Decimal; veinticuatro variaciones |
| `distance_ma_12m` | P[m] / media(P[m−11], …, P[m]) − 1 | Decimal |
| `price_volatility_12m` | Desviación típica muestral de r[m−11], …, r[m] por √12 | Decimal anualizado |
| `drawdown_12m` | P[m] / máximo(P[m−11], …, P[m]) − 1 | Decimal, no positivo |
| `credit_spread_pp` | Baa[k] − Aaa[k] | Puntos porcentuales |
| `credit_spread_change_pp` | Diferencial[k] − diferencial[k−1] | Puntos porcentuales |
| `industry_breadth_12m` | Fracción de industrias con W[k] > su media de doce W | Fracción entre 0 y 1 |
| `industry_dispersion` | Desviación típica muestral entre los doce retornos en k | Decimal mensual |

Las medias y ventanas incluyen ambos extremos. El drawdown mide la distancia actual al máximo de la ventana, no la peor caída ocurrida dentro de ella. Tanto la dispersión como la volatilidad usan `ddof=1`; la dispersión no se anualiza. Las dos características asociadas a las reglas reutilizan sus indicadores de precio originales.

Los retornos industriales del primer bloque mensual ponderado por valor se convierten de porcentaje a decimal una sola vez. W es el producto acumulado de (1 + retorno) desde julio de 1926. Su escala inicial arbitraria no altera la comparación con su media. La igualdad con la media no cuenta como superación. Antes de tener doce observaciones, la amplitud permanece ausente, no se convierte en cero. La amplitud y dispersión corresponden a carteras industriales de French, no a acciones individuales, ETF ni exactamente al universo del S&P 500.

Baa y Aaa entran como rendimientos anuales en porcentaje. Su diferencia se conserva en puntos porcentuales, sin dividir entre doce ni tratarla como RF. No equivale a un diferencial corporativo frente a Treasury ni a un OAS. Los dividendos de Shiller, RF y los resultados de las estrategias no se utilizan como predictores.

## Sustitución de la distancia a media de tres meses

Antes de definir etiquetas o entrenar modelos se sustituye `distance_ma_3m` por `market_return_24m`, manteniendo diez candidatas. Es una decisión de diseño: se prioriza describir el estado del mercado a dos años y conectar con el comparador bajista ya previsto en la guía. La alternativa descartada añadía otra descripción de tendencia reciente junto al retorno de un mes, momentum y la distancia a la media de doce meses. No se ha comparado su capacidad predictiva ni se afirma que la sustitución mejore resultados o elimine la redundancia.

La fórmula es exactamente la del retorno previo utilizado por nuestro comparador bajista: `P[m] / P[m−24] − 1`. El filtro sencillo convierte ese retorno en un veto cuando es negativo; el modelo recibirá el valor continuo, que permite distinguir una caída pequeña de otra intensa. No se añade también el indicador binario como undécima característica. El sentido y las ventanas de las reglas originales permanecen iguales.

Daniel y Moskowitz (2016), *Momentum crashes*, sección 3.2, utilizan el signo del retorno acumulado previo de dos años para identificar mercados bajistas. Nuestra variable utiliza variaciones de precios medios de Shiller, sin dividendos: es una adaptación, no una réplica de su retorno de mercado ni evidencia de que funcione como filtro para nuestro índice. Referencia: [DOI 10.1016/j.jfineco.2015.12.002](https://doi.org/10.1016/j.jfineco.2015.12.002).

La primera decisión, diciembre de 1926 para el objetivo enero de 1927, utiliza precios de diciembre de 1924 y diciembre de 1926. La historia ya conservada cubre esta ventana: no se descargan nuevas fuentes ni se pierden meses adicionales. La dispersión industrial se conserva como candidata exploratoria. Las posibles dependencias entre retorno de 24 meses, momentum y otras variables se evaluarán dentro del desarrollo con el protocolo de validación y Clustered MDA.

## Calentamiento y guardado

La salida `data/processed/monthly_features.parquet` conserva las 756 filas. Con los originales actuales, nueve variables cubren todo el desarrollo y la amplitud empieza en agosto de 1927. `features_ready` identifica las 749 filas con las diez variables completas. Los siete meses anteriores se conservan con amplitud ausente; no se rellenan ni se cambia el periodo de la guía. Las comparaciones con las diez variables deberán utilizar una misma muestra completa.

Las columnas `asset`, `target_period`, `decision_period`, `price_source_period`, `context_source_period` y `features_ready` son identificación y control, no entradas del modelo. La lista explícita `FEATURE_COLUMNS` delimita los diez predictores. Los meses y las fuentes se comprueban antes del cálculo. Se rechazan huecos internos, duplicados, valores inválidos e importes desde 1990 en las entradas. La historia previa solo sirve para calcular ventanas.

El JSON acompaña al Parquet con diccionario, fórmulas, unidades, fechas, ausencias y limitaciones. No es configuración de entrada. Volver a preparar Shiller retira la tabla y su resumen: hay que ejecutar el 07 de nuevo. Si se actualizan los originales de contexto, también se debe repetir el 07. Esta ejecución no cambia señales ni simulaciones anteriores.

No se ha realizado selección por resultados, normalización global, PCA, Clustered MDA o SHAP. Los ajustes que se aprendan de los datos se harán dentro de las particiones de entrenamiento. La tabla tampoco garantiza que una característica resulte útil o aporte información distinta de otras. Las etiquetas, la selección y la validación temporal son incrementos posteriores.

## Fuentes

- [Shiller](https://shillerdata.com/): promedios mensuales de precios.
- [Kenneth French, doce industrias](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_12_ind_port.html): cobertura mensual desde julio de 1926 y construcción de las carteras. Se utiliza el bloque ponderado por valor del ZIP oficial.
- Moody's, [BAA](https://fred.stlouisfed.org/series/BAA) y [AAA](https://fred.stlouisfed.org/series/AAA), obtenidas en FRED: series mensuales en porcentaje, sujetas a revisión.

Estas decisiones y sus límites podrán incorporarse a Materiales y métodos de la memoria. El diagnóstico de cobertura y medias frente a cierres se conserva en `docs/diagnostico_fuentes.md`; este incremento no modifica la memoria.
