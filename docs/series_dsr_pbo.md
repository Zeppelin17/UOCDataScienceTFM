# Series mensuales para DSR y PBO

Las secciones 47–48 del notebook 14 preparan y guardan una matriz de retornos netos de enero de 1950 a diciembre de 1989. El conjunto de variantes se fija antes de simular las cuentas nuevas. La comparación se hará por separado para momentum y reversión, porque cada una parte de una regla de inversión distinta.

## Qué entra en la comparación

| Familia | Filtros por regla |
|---|---|
| Logística de referencia | M1, M2 y M3 |
| Retiradas individuales de M2 | Sin volatilidad, sin retorno de 24 meses y sin distancia al máximo |
| Bloques sucesivos | Con media, con crédito, con industrias y con el bloque de régimen de precios |
| Random forest | RF_M1, RF_M2 y RF_M3 |
| Gradient boosting | GB_M1 y GB_M2 |
| EBM | EBM_M1 |

Entran las 16 variantes cronológicas de cada regla, incluidas las que rindieron peor y las que surgieron para explicar un resultado. M0 es la referencia de frecuencia. Con el umbral fijo, su cuenta coincide con la regla original en momentum y con efectivo en reversión. La matriz conserva cinco comparadores fijos para cada regla: la regla original, el veto bajista, el ajuste por volatilidad, comprar y mantener y efectivo. Los comparadores acompañan la evaluación de las estrategias como referencias.

El último escalón por bloques representa la especificación de logística con diez variables que también se evaluó mediante CPCV. Clustered MDA queda fuera de esta matriz porque su selector se ajustó con un esquema interno específico del CPCV. Para incorporarlo habría que definir y evaluar un selector cronológico adicional. Su resultado predictivo sigue siendo parte del TFM. Las sombras y los reajustes anuales mantienen sus funciones de contraste y predicción. Este alcance define qué búsqueda económica podrá cubrir el análisis de sobreajuste posterior.

## Cómo se construyen las cuentas

Se leen las probabilidades cronológicas guardadas y se reproducen en memoria los cuatro recorridos por bloques partiendo de la misma referencia M1. Las cuentas usan el umbral estricto de 0,5 y el motor contable de las secciones 19–22. Una señal activa exige una probabilidad válida. Tras aplicar el filtro se conserva la dirección de la regla y se simula una cuenta continua, con los mismos dividendos aproximados, efectivo, costes y liquidación que en la evaluación anterior. Las cuentas M1–M3 y la de reversión con RF_M1, si está guardada, deben reproducir exactamente sus retornos previos.

La tabla `development_selection_returns.parquet` reúne **20.160 filas**. Cada regla tiene 16 filtros y 5 comparadores, todos con 480 meses. Cada fila contiene la regla, la función de la cuenta en la comparación, el identificador de la variante o referencia, el mes, el retorno neto y el retorno del efectivo. El JSON conserva los supuestos y el origen de las predicciones. Cambiar las tablas de origen exige regenerar esta salida.

Las secciones 49–51 usan estas series sincronizadas para el DSR y el PBO. El periodo desde 1990 queda reservado hasta autorización expresa. [Método y resultados](dsr_pbo.md)
