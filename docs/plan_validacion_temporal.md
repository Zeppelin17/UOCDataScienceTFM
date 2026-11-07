# Plan del notebook 10: validación temporal

Fecha: 7 de noviembre de 2026. Estado: plan de implementación; no se han creado particiones persistidas ni entrenado modelos. Se ha comprobado su viabilidad mediante recuentos sobre los datos preparados, sin modificar archivos de datos.

## 1. Objetivo y alcance

Preparar las particiones de descubrimiento de 1927–1989 antes de entrenar el filtro de momentum y el de reversión. El notebook explicará qué fechas se utilizan para aprender, cuáles para validar y cuáles se excluyen por proximidad temporal o por no contener un ejemplo utilizable.

Se mantendrán las diez candidatas. Las cuatro asociaciones favorables del notebook 09 no serán una selección de variables. El periodo desde 1990 permanece fuera de este incremento.

Las decisiones de seis bloques, purga de un mes y embargo de entre tres y seis meses proceden de la guía del tutor del 7 de noviembre. Elegir dos bloques de validación y fijar seis meses de embargo son decisiones concretas del TFM, anteriores al entrenamiento y a sus métricas. No se compararán embargos para escoger el más rentable.

## 2. Calendario de CPCV

Se dividirán los 756 meses objetivo en seis bloques consecutivos de 126 meses. Las fronteras se fijan sobre el calendario completo, antes de retirar meses sin señal o con calentamiento:

| Bloque | Primer objetivo | Último objetivo | Meses |
|---|---|---|---:|
| 1 | 1927-01 | 1937-06 | 126 |
| 2 | 1937-07 | 1947-12 | 126 |
| 3 | 1948-01 | 1958-06 | 126 |
| 4 | 1958-07 | 1968-12 | 126 |
| 5 | 1969-01 | 1979-06 | 126 |
| 6 | 1979-07 | 1989-12 | 126 |

En cada partición se reservan dos bloques para validación y se parte de los otros cuatro para entrenamiento. Las quince parejas posibles se enumeran en orden, sin aleatoriedad. Las mismas fronteras y exclusiones de calendario sirven para ambas reglas y, después, para todos los modelos.

En descubrimiento, CPCV puede entrenar con bloques posteriores a los de validación, según indica la guía. No reproduce una inversión en tiempo real. La evaluación posterior utilizará walk-forward con datos pasados y una cartera continua.

Cada mes pertenece a validación en cinco combinaciones. Esa repetición no multiplica las observaciones independientes. La forma de agregar predicciones y construir las trayectorias de CPCV se concretará antes de calcular métricas de modelos; este notebook no calcula AUC, log-loss ni Sharpe.

## 3. Purga y embargo: definición exacta

Cada ejemplo tiene un mes de decisión y uno objetivo. Para las etiquetas actuales, `label_end_period` debe coincidir con el objetivo: el horizonte es de un mes. Una etiqueta fuera del desarrollo, ausente en una señal activa o con un intervalo incompatible detendrá la preparación.

Para cada pareja de bloques de validación:

1. Fusionar los bloques si son adyacentes, formando intervalos continuos de validación.
2. Reservar todos sus meses objetivo para validación.
3. Aplicar una separación conservadora de un mes antes y después de cada intervalo. Con el horizonte actual equivale a excluir del entrenamiento los meses objetivo inmediatamente anterior y posterior; protege también las fronteras de los intervalos de etiqueta tratados de forma inclusiva.
4. Aplicar embargo a los seis meses objetivo inmediatamente posteriores al final de cada intervalo de validación. El primer mes coincide con la purga posterior: se excluye una sola vez. El embargo se cuenta desde el final de validación, no desde el final de la purga.
5. Limitar las exclusiones al calendario de desarrollo. La pertenencia a validación tiene prioridad; ningún mes reservado para validar se reclasifica como entrenamiento.

Por ejemplo, si un intervalo de validación va de enero de 1948 a junio de 1958, se excluye diciembre de 1947 por la frontera previa. Julio de 1958 coincide con purga posterior y embargo; agosto–diciembre de 1958 completan la ventana de seis meses. El entrenamiento posterior puede comenzar en enero de 1959, si no hay otra exclusión.

La tabla asignará a cada mes un papel exclusivo: entrenamiento, validación, purga o embargo. Para que los recuentos no dupliquen meses se aplicará esa prioridad: validación, purga, embargo y entrenamiento. El informe distinguirá la longitud de la ventana de embargo de los meses adicionales que elimina tras considerar la purga.

Estas separaciones se calculan en meses calendario. Un mes sin señal, una ausencia de calentamiento o una fecha sin ejemplo entrenable no acorta la separación. El embargo reduce dependencia cercana, pero no hace independientes todos los indicadores de ventanas largas ni convierte los datos reconstruidos en información point-in-time.

## 4. Ejemplos utilizables y preparación de características

Se leerán las tablas de los notebooks 07 y 08. El recorrido de preparación será **01 → 02 → 07 → 08 → 10**. El 09 no es un requisito: sus contrastes, valores p y listas de asociaciones no alimentarán la validación.

Se reconstruirá la preparación causal ya definida mediante `transform_features`, a partir de las características del 07, sin leer las tablas `screening_*`: 36 observaciones anteriores, límites 1/99 y z-score con historia pasada. Las diez transformaciones son definiciones fijas de los predictores, sin utilizar etiquetas para ajustar sus fórmulas o parámetros. La historia de covariables observadas se actualiza cronológicamente, independientemente del papel de cada fecha en CPCV; no se ajusta un escalador usando todo el desarrollo.

Esta preparación temporal se distingue de ajustes aprendidos para un modelo: cualquier escalado adicional, agrupación, compuesto, selección de características, hiperparámetro o umbral basado en resultados se ajustará exclusivamente con el entrenamiento de su partición. La selección supervisada y Clustered MDA necesitarán validación interna dentro de ese entrenamiento. No se implementan en este incremento.

Un ejemplo utilizable requiere simultáneamente:

- Las diez características transformadas disponibles.
- Señal de operación de la regla, distinta de efectivo.
- Etiqueta central del 08 válida, con resultado dentro de 1927–1989.
- Pertenencia al entrenamiento o validación después de aplicar las exclusiones temporales.

La etiqueta alternativa sin negociación se conservará como sensibilidad ya definida, sin usarla para mover fronteras ni escoger muestras favorables. No se seleccionarán automáticamente columnas numéricas: las diez entradas corresponden a `FEATURE_COLUMNS` y sus transformaciones `z_...`. Posiciones, fechas, etiquetas, retornos realizados, costes y marcas de control no serán predictores.

Los 713 meses comunes de la preparación no equivalen a 713 ejemplos por regla. El notebook mostrará, por partición y regla, meses de calendario, meses disponibles, señales, ejemplos utilizables y etiquetas positivas/negativas. No se borrarán particiones por tener una distribución poco favorable. Si faltan ambas clases en entrenamiento se marcará que no permite entrenar un clasificador convencional; si ocurre en validación se indicará que AUC no sería estimable, sin inventar clases o mover fechas.

`label_end_period` es un límite temporal del resultado, no una fecha de publicación certificada. La interpolación de dividendos y las revisiones de las fuentes siguen limitando la interpretación. La disponibilidad efectiva de etiquetas para el reentrenamiento walk-forward deberá tratarse explícitamente al desarrollar esa etapa.

## 5. Comprobación previa de viabilidad

Se comprobaron las quince combinaciones con las etiquetas centrales y la preparación causal actual. Los recuentos siguientes son rangos entre particiones, no objetivos para ajustar el diseño:

| Regla | Ejemplos de entrenamiento | Ejemplos de validación | Ambas clases en todas las particiones |
|---|---:|---:|---|
| Momentum | 249–342 | 98–187 | Sí, en entrenamiento y validación |
| Reversión | 444–497 | 206–252 | Sí, en entrenamiento y validación |

Esta comprobación usa los resultados binarios solo para describir cobertura de clases, sin entrenar modelos, comparar rendimiento o probar otras fronteras. Las fronteras y el embargo se eligieron antes de realizarla.

## 6. Incremento de implementación

1. **Módulo `src/tfm/validation.py`.** Construir el calendario de bloques y las quince particiones, con purga/embargo y controles de etiquetas. Separar la pertenencia temporal de la disponibilidad de un ejemplo por regla. Reutilizar la preparación causal existente.
2. **Notebook `10_validacion_temporal.ipynb`.** Explicar la diferencia entre descubrimiento y evaluación cronológica; mostrar los seis bloques, las quince combinaciones y un gráfico con colores para entrenamiento, validación, purga y embargo. Permitir inspeccionar una partición por su número y mostrar los recuentos de ambas reglas.
3. **Salidas sencillas.** Guardar `validation_splits.parquet` con 15 × 756 = 11.340 filas de calendario y `validation_summary.parquet` con 15 × 2 = 30 resúmenes. Cada tabla tendrá su JSON descriptivo con periodos, decisiones y limitaciones, mediante el guardado existente. No se duplicarán las etiquetas y características en cada partición.
4. **Invalidación coherente.** Regenerar las entradas de 01, 02, 07 u 08 retirará estas salidas. Repetir el cribado 09 no las invalidará: no dependen de sus resultados. Las fuentes originales se mantendrán intactas.
5. **Documentación y verificación.** Añadir el recorrido al README y describir fórmulas de exclusión, recuentos y controles. Ejecutar el notebook con una copia temporal de los datos preparados; no editar la memoria.

No se añaden dependencias, CLI, ficheros de configuración o un gestor de experimentos. Los parámetros fijados serán visibles en el notebook y las funciones reutilizables estarán en el módulo.

## 7. Pruebas esenciales y criterio de cierre

Se añadirán dos comprobaciones principales:

- **Particiones y fronteras.** Seis bloques exactos, quince parejas únicas y cinco apariciones de cada mes en validación. Entrenamiento y validación disjuntos; comprobar intervalos adyacentes, límites del desarrollo, purga y embargo medidos en calendario aunque falten señales.
- **Ejemplos y recorrido.** Comprobar características y etiquetas alineadas, rechazo de intervalos fuera del desarrollo, ausencia de señales convertidas en negativos y recuentos de clases. Ejecutar el notebook sin red, verificar el guardado y la retirada de salidas al regenerar entradas. Cambiar los valores de las etiquetas no deberá cambiar la pertenencia temporal.

El incremento estará terminado cuando las tablas tengan tamaños y fronteras correctos, no haya ejemplos de entrenamiento en intervalos excluidos y el notebook se ejecute desde un kernel limpio. Se detendrá en ese punto para el commit del estudiante.

Después se preparará el primer experimento de regresión logística, con registro de variantes desde su inicio. Su selección y evaluación se concretarán antes de ejecutar modelos. El reentrenamiento anual futuro generará señales para una sola simulación continua; no reiniciará el capital ni liquidará la cartera cada año.

## 8. Referencias

Guía del tutor: `Guia TFM ML gestion Inversiones L1 v26-27 (07 11 26).pdf`, tabla de bloques y aclaración sobre descubrimiento CPCV frente a evaluación walk-forward. La memoria ya contiene `bib:lopezdeprado2018`, pertinente para purga/embargo y CPCV (capítulos 7 y 12); no se necesita duplicar esa entrada para este plan.

El contexto de etiquetas y el cribado descriptivo están en [etiquetado.md](etiquetado.md) e [hipotesis_y_cribado.md](hipotesis_y_cribado.md). Las adaptaciones del código de Jansen se documentan en [referencias_jansen.md](referencias_jansen.md); sus ejemplos walk-forward no sustituyen el CPCV requerido por la guía.
