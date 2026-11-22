# Sombras de la logística M1 en momentum

El contraste comprueba si las dos entradas de M1 aportan información predictiva para momentum cuando están en sus fechas reales. Se fija tras revisar los resultados predictivos y económicos del desarrollo y antes de calcular estas sombras. Se usa la logística L2 con `C=1`, el etiquetado central y el CPCV de M1 ya calculado en las secciones 16–18. La evaluación desde 1990 queda pendiente de autorización expresa de Pol.

## Comparación fijada

El modelo real y cada sombra usan las mismas quince particiones, con purga de un mes y embargo de seis. Para cada señal se promedian las cinco probabilidades obtenidas cuando su mes queda en validación. La métrica principal se calcula sobre todo el desarrollo utilizable de M1 en momentum. M0 se calcula como la proporción de etiquetas favorables dentro del entrenamiento de cada partición y conserva también su promedio de cinco predicciones por señal.

Para crear una sombra se desplazan juntas las dos columnas transformadas de M1 sobre los 713 meses del calendario común. Las señales, las etiquetas, los meses de entrenamiento y los de validación conservan sus fechas. Se reutilizan las 642 rotaciones del notebook 12, de 36 a 677 meses, con distancia circular mínima de 36. Cada rotación repite los quince ajustes de momentum. Se comprueba que el recorrido sin desplazar reproduzca las probabilidades guardadas de M1 y M0.

Aplicamos el mismo criterio operativo que a la logística de diez entradas. El M1 real debe alcanzar AUC de al menos 0,54, mejorar la log-loss de M0 y superar estrictamente el percentil 95 de las mejoras de las sombras. La mejora se calcula como `log_loss(M0) − log_loss(modelo)`. El AUC de las sombras se presenta como diagnóstico. El percentil exige disponer de la familia completa de rotaciones.

Las rotaciones son referencias artificiales y están relacionadas entre sí. El resultado informa sobre la capacidad predictiva del modelo dentro del desarrollo y se interpreta junto a su cuenta económica. [Protocolo del notebook 12](sombras_logistica.md) · [CPCV de M1](cpcv_regimen.md)

## Resultados

| Medida | Valor |
|---|---:|
| Señales activas en el resumen CPCV | 442 |
| AUC de M1 con las fechas reales | 0,593238 |
| Log-loss de M0 | 0,680904 |
| Log-loss de M1 real | 0,663221 |
| Mejora de M1 real frente a M0 | 0,017683 |
| Percentil 95 de las mejoras de las sombras | 0,002731 |
| Mayor mejora entre las 642 sombras | 0,009167 |

M1 cumple las tres condiciones. Su mejora de log-loss frente a M0 supera la de las 642 sombras. Con las fechas reales, las dos entradas aportan evidencia predictiva frente a estas referencias artificiales en desarrollo.

Se completaron 9.630 ajustes de sombras y 15 ajustes para reproducir la referencia sin desplazamiento. Las secciones 42–43 del notebook 14 muestran el histograma y guardan `momentum_m1_shadows` y `momentum_m1_shadow_comparison`. El historial queda en `outputs/experiments/momentum_m1_shadow_trials.jsonl`. Las tablas y los historiales de los experimentos anteriores se conservaron durante la verificación.
