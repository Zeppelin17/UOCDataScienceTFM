# Robustez CPCV de las comparaciones de régimen

Protocolo fijado tras los resultados walk-forward de M0–M3 y las retiradas individuales, antes de calcular esta comparación CPCV con datos reales. Se conocen también los experimentos CPCV anteriores del 11–13, que usaban diez características o su selección. Este análisis no es una confirmación independiente ni un prerregistro anterior a toda exploración. Sigue la guía del tutor del 15 de noviembre de 2026, apartado 5, pp. 19–21.

## Pregunta y candidatos

¿Se mantienen las diferencias entre las configuraciones fijadas al cambiar la separación entre entrenamiento y prueba? Se evalúan los seis candidatos completos, sin elegir ahora los que hayan salido mejor en walk-forward:

| Candidato | Predictores |
|---|---|
| M1 | Retorno mensual y momentum 12–1 |
| M2 | M1 + volatilidad + retorno de 24 meses + drawdown |
| M3 | M2 + interacción mercado bajista × volatilidad |
| M2 sin volatilidad | Las otras cuatro columnas de M2 |
| M2 sin retorno de 24 meses | Las otras cuatro columnas de M2 |
| M2 sin drawdown | Las otras cuatro columnas de M2 |

Se utiliza la misma logística L2 C=1 y el mismo etiquetado central. No se buscan hiperparámetros, nuevas listas, horizontes, umbrales o agrupaciones. M0 es la frecuencia positiva del entrenamiento de cada regla y partición. La logística del notebook 11, con diez características, se conserva como experimento previo; no equivale a M1.

## Datos y particiones

Se requieren características y etiquetas de 07/08 y las dos tablas del 10. Se reconstruye la muestra con `load_logistic_inputs`, comprobando que las particiones y sus recuentos corresponden a las entradas actuales. No se leen resultados de 09, 11–13 ni del walk-forward.

Se mantienen seis bloques de 126 meses, quince parejas de validación, purga de un mes y embargo de seis, con el calendario y prioridades ya fijados. Los indicadores, el z-score y la interacción de M3 se construyen causalmente por fecha antes de asignar bloques. No se ajusta su historia con los bloques futuros de entrenamiento. Se reutiliza la convención de historia recortada cero de M3 y se exige que sus valores estén disponibles para toda la muestra común: no se descartan ejemplos para un candidato.

CPCV puede ajustar coeficientes con datos posteriores a su validación. Eso es compatible con su papel de robustez, pero impide presentarlo como inversión en tiempo real. Los quince folds y sus crisis compartidas no son ensayos independientes. Los mismos datos de desarrollo ya han intervenido en otros análisis, y los periodos desde 1990 siguen reservados.

## Ajuste y métricas

Cada candidato tiene quince ajustes por regla: treinta, y 180 entre los seis. Se mantienen las predicciones de cada partición y cinco predicciones por ejemplo. Se comprueban las claves de mes, regla, partición y etiqueta frente al calendario previsto. Las referencias M0 coinciden para todos los candidatos y sus métricas se publican una sola vez.

Se reutiliza `summarize_predictions` para calcular métricas por partición y la media de cinco probabilidades por ejemplo. Falta de una probabilidad implica media ausente: no se eliminan meses ni se promedian cuatro modelos. Las particiones vacías se conservan y una única clase deja AUC ausente, aunque permita log-loss. La falta de convergencia detiene y registra el intento, sin cambiar parámetros.

La media de cinco probabilidades es un resumen de los modelos CPCV, no una trayectoria de retornos ni cinco observaciones independientes. No se calcularán Sharpe, DSR o PBO tratando esas probabilidades como rentabilidades. La AUC y la log-loss reunidas se calculan una vez por regla y candidato.

Se fijan dos resúmenes antes de calcularlos:

- `monthly_mean`: todo el desarrollo utilizable. Con los datos actuales son 442 ejemplos de momentum y 710 de reversión desde agosto de 1930.
- `common_period`: las mismas medias CPCV restringidas a enero de 1950–diciembre de 1989. Son 331 y 479 ejemplos, respectivamente, coincidiendo con los meses objetivo de la prueba walk-forward. No cambia los modelos o bloques ni requiere nuevos ajustes.

El segundo resumen evita atribuir a la validación diferencias que podrían proceder de evaluar meses distintos. Alinear los meses no iguala el entrenamiento: CPCV sigue usando bloques futuros y una media de cinco modelos, mientras walk-forward usa una predicción cronológica por ejemplo. No se escoge el resumen favorable ni se presenta como otra réplica independiente. El principal sigue siendo el CPCV completo.

## Comparaciones y estabilidad

Se contrastan M2 frente a M1, M3 frente a M1 y M3 frente a M2. Para cada retirada, se contrasta M2 completo frente al candidato sin esa variable. El candidato indicado siempre tiene orientación favorable positiva: AUC del candidato menos referencia y log-loss de referencia menos candidato. En las retiradas esto representa el valor de conservar la variable, condicionado al resto de M2.

Las comparaciones se emparejan por muestra y partición, exigiendo iguales ejemplos y clases. Se conservan los dos resúmenes y las quince particiones. Por cada regla y comparación se muestran mejoras, empeoramientos, empates y no estimables. La mayoría exige ocho de las quince particiones previstas, sin quitar las no estimables del denominador. Estas diferencias no son un contraste con valor p ni un control conjunto de error.

Los resultados se interpretarán junto al walk-forward, conservando los resultados desfavorables. No se elegirá otro modelo o validación solo porque mejore aquí. La aceptación exige los criterios de ambos esquemas, sombras específicas y Sharpe neto según la guía. Las retiradas siguen siendo diagnóstico; elegir un subconjunto después requerirá selección dentro del entrenamiento y evaluación separada.

## Salidas e historial

`src/tfm/cpcv_regime.py` implementa el recorrido. La sección 16–18 del notebook 14 puede ejecutarse en un kernel nuevo con 07/08/10 preparados; no necesita ejecutar sus secciones walk-forward. El código de los modelos anteriores no se modifica y sus resultados no se sobrescriben.

Se publican cinco tablas con JSON:

| Tabla | Filas con los datos actuales | Contenido |
|---|---:|---|
| `cpcv_regime_predictions` | 34.560 | Predicciones por candidato, regla, partición y mes; incluye M0. |
| `cpcv_regime_monthly` | 6.912 | Medias de cinco probabilidades y disponibilidad por ejemplo y candidato. |
| `cpcv_regime_metrics` | 238 | Siete métodos, incluido M0, por partición y ambos resúmenes. |
| `cpcv_regime_coefficients` | 930 | Interceptos y columnas efectivamente ajustadas, con estado. |
| `cpcv_regime_comparison` | 204 | Seis comparaciones, dos reglas, quince particiones y dos resúmenes. |

La repetición de filas por candidato y partición no amplía el tamaño independiente de la muestra. Se guardan los recuentos originales y los estados de disponibilidad.

Cada candidato se registra antes de ajustarlo en `outputs/experiments/cpcv_regime_trials.jsonl`, con resultados o fallo. Se reutiliza su identificador de configuración histórica, cuyo nombre puede contener `walk_forward`, y se identifica explícitamente `validation_scheme=CPCV` y `purpose=same_candidate_cpcv_robustness`. No se introducen seis listas o hiperparámetros nuevos: `candidate_configurations_added_per_rule=0`. La nueva validación queda registrada y no se presenta como observación independiente. Este registro no determina por sí solo el número efectivo de ensayos del futuro DSR/PBO; habrá que considerar todas las configuraciones y decisiones observadas.

Si falla un candidato, se detiene el recorrido, se conserva el fallo y no se devuelve una familia parcial para publicar. Las tablas y JSON mantienen el patrón del proyecto: si falla la celda de publicación, se repite completa. El historial no se elimina al regenerar datos.

Preparar nuevamente 01/02/07/08 o guardar cualquiera de las tablas de particiones del 10 retira las cinco salidas CPCV. Repetir 09, publicar resultados del 11–13 o los de walk-forward las conserva: no son entradas de este cálculo. Publicar las cinco salidas nuevas tampoco elimina esas referencias. No se añaden dependencias, CLI, configuraciones de entrada, CSV o modelos serializados.

## Comprobaciones esenciales

Se comprueba la independencia del ajuste respecto a etiquetas reservadas, las cinco apariciones por ejemplo, las columnas de cada candidato y la cobertura del resumen común. La sección CPCV se prueba con tablas sintéticas y sin resultados walk-forward, verificando métricas, historial, persistencia, conservación de referencias e invalidación por 07/08/10. Los controles financieros, de normalización y de fronteras existentes se conservan.

Las referencias metodológicas siguen siendo las de la guía y López de Prado (2018), capítulos 7 y 12. La agregación de probabilidades y el resumen común son decisiones de este TFM. No se necesita una nueva referencia bibliográfica para esta ampliación y no se modifica la memoria automáticamente.

## Resultado de la ejecución local

Se ha ejecutado la sección 16–18 con los datos preparados, sin descargar fuentes ni recalcular walk-forward. Los 180 ajustes convergen y todas las comparaciones disponen de las quince particiones. Las cinco tablas tienen las filas previstas arriba.

Resumen principal de las medias CPCV sobre todo el desarrollo utilizable:

| Modelo | AUC momentum | Log-loss momentum | AUC reversión | Log-loss reversión |
|---|---:|---:|---:|---:|
| M0 | 0,433950 | 0,680904 | 0,473115 | 0,660392 |
| M1 | 0,593238 | 0,663221 | 0,616303 | 0,649677 |
| M2 | 0,589053 | 0,665993 | 0,606935 | 0,653758 |
| M3 | 0,599091 | 0,663932 | 0,608541 | 0,652633 |
| M2 sin volatilidad | 0,589413 | 0,665124 | 0,609959 | 0,651976 |
| M2 sin retorno de 24 meses | 0,587511 | 0,667220 | 0,602324 | 0,652610 |
| M2 sin drawdown | 0,589518 | 0,664935 | 0,614503 | 0,652019 |

Una AUC mayor y una log-loss menor son favorables. Aunque M0 sea constante dentro de cada partición, sus frecuencias de entrenamiento varían entre particiones y las medias por mes no son constantes: su AUC reunida no tiene por qué ser 0,5.

M2 empeora ambas métricas frente a M1 en las dos reglas. M3 recupera parte de la pérdida: supera a M2 en ambas métricas, pero frente a M1 solo mejora la AUC de momentum; su log-loss es algo peor y en reversión no supera a M1 en ninguna de las dos métricas. No hay una mejora consistente por añadir régimen.

| Comparación: candidato frente a referencia | Particiones con mejora AUC, momentum | Particiones con mejora AUC, reversión |
|---|---:|---:|
| M2 frente a M1 | 7/15 | 9/15 |
| M3 frente a M1 | 10/15 | 8/15 |
| M3 frente a M2 | 10/15 | 8/15 |
| Conservar volatilidad en M2 | 10/15 | 7/15 |
| Conservar retorno de 24 meses en M2 | 12/15 | 11/15 |
| Conservar drawdown en M2 | 6/15 | 2/15 |

La dirección de una diferencia reunida puede no coincidir con la mayoría por partición: son resúmenes distintos, y la AUC reunida incluye comparaciones entre meses de bloques diferentes. No se interpretan estos recuentos como ensayos independientes. En las retiradas, conservar el retorno de 24 meses mejora la AUC reunida de ambas reglas; la volatilidad y el drawdown la empeoran. La log-loss no respalda todas las mejoras de AUC. Estos diagnósticos no autorizan a escoger ahora el subconjunto más favorable.

En el resumen secundario 1950–1989 las AUC de M1/M2/M3 son 0,578422/0,573897/0,584144 para momentum y 0,632218/0,638938/0,638695 para reversión. En reversión cambia la dirección de la comparación con M1 respecto al resumen completo. Esto muestra sensibilidad al periodo; no sustituye el resultado principal ni equivale a walk-forward. En este último tampoco se había alcanzado la mayoría de años de mejora frente a M1 para M2 o M3.

Por tanto, no se acepta ninguna incorporación de régimen con estos resultados. Siguen pendientes las sombras específicas de estos candidatos y la evaluación económica; no se han calculado aquí DSR/PBO ni SHAP. La comparación CPCV completa la comprobación de robustez estadística prevista en este incremento y mantiene las evidencias desfavorables.

La revisión reconstruye las probabilidades desde los coeficientes y las columnas guardadas; comprueba los priors con las etiquetas de entrenamiento, los meses reservados, las cinco predicciones por ejemplo, las medias y las métricas reunidas mediante fórmulas independientes. También contrasta los signos de las diferencias y verifica que los cien archivos anteriores de datos y experimentos conservan exactamente su contenido.

Pasan las 70 pruebas del proyecto. Se mantienen únicamente las dos advertencias anteriores de visualización no interactiva del notebook 09. El notebook 14 compila y se conserva sin salidas ni contadores; no se ha modificado la memoria.
