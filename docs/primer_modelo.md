# Primer modelo: regresión logística L2

Diseño fijado el 14 de noviembre de 2026, antes de entrenar este experimento. Es el siguiente incremento al notebook 10 y conserva las decisiones de la memoria. Se entregan probabilidades de validación de descubrimiento; todavía no decisiones de cartera ni una evaluación desde 1990.

## Pregunta y datos

¿Las diez características ayudan a distinguir qué señales mensuales superan al efectivo, mejor que conocer únicamente la proporción de éxitos del entrenamiento?

Se ajusta un modelo por regla y partición: momentum y reversión, quince particiones CPCV cada una. Las entradas son las tablas 07/08 y las particiones guardadas por el 10. Se reconstruyen las diez transformaciones causales fijas, sin leer resultados del 09, seleccionar sus asociaciones significativas o volver a ajustar un escalador con todo el desarrollo. Se conservan purga de un mes y embargo de seis. Antes del entrenamiento se compara el resumen de particiones guardado con el calculado sobre las entradas actuales; si difiere, se requiere repetir el 10.

La variable objetivo es `label` del 08: operación aislada neta de costes, dividendos y préstamo frente a RF. La alternativa sin negociación no se entrena aquí. Solo entran los meses con señal activa, etiqueta binaria y las diez características transformadas disponibles. Las fechas, los resultados realizados y las marcas de control no son predictores. Ningún importe desde 1990 se consulta.

## Modelo fijo y referencia

La logística transforma una suma de características en una probabilidad entre cero y uno:

`p(éxito | x) = 1 / (1 + exp(-(intercepto + suma(coeficiente_j * x_j))))`.

Un coeficiente describe un efecto sobre el logaritmo de las probabilidades relativas, condicionado al resto de variables. No equivale a un cambio constante en puntos de probabilidad ni demuestra causalidad. La correlación entre características puede hacer inestables los coeficientes individuales.

Se fija L2, `C=1`, intercepto, `lbfgs`, tolerancia numérica `1e-8` y máximo de 2000 iteraciones. `C` es el inverso de la intensidad de regularización: menor C impone mayor penalización. El valor uno es un punto de partida convencional, no una intensidad óptima demostrada. No hay rejilla de hiperparámetros, selección de variables ni ajuste del umbral de operación. L2 reduce coeficientes, pero no elimina automáticamente características.

Todos los ejemplos pesan lo mismo. No se utiliza sobremuestreo, ponderación por clase ni calibración adicional. Así se conserva la distribución de etiquetas observada, sin garantizar que el modelo produzca probabilidades calibradas.

La referencia asigna a toda su validación la frecuencia de etiquetas positivas del entrenamiento de esa partición. Por ejemplo, 60 éxitos de 100 ejemplos implican una probabilidad constante de 0,60. Se calcula por regla y partición, nunca sobre validación o sobre todo el desarrollo. Su AUC por partición es 0,5 cuando existen ambas clases. Su AUC agregada puede diferir de 0,5 porque la probabilidad de referencia varía entre particiones y meses.

## Validación y resumen de predicciones

Se guardan las cinco predicciones de validación correspondientes a cada ejemplo. El resumen principal es su media aritmética por regla y mes objetivo. Se aplica exactamente la misma agregación a la referencia. Cada ejemplo cuenta una vez en las métricas principales; las métricas por partición se conservan como descripción complementaria.

Esta media es un resumen del conjunto de modelos de descubrimiento, no una trayectoria CPCV. No se suman cinco veces las ganancias de un mes ni se interpretan las repeticiones como observaciones independientes. Tampoco se construyen intervalos de confianza suponiendo independencia entre particiones. Las trayectorias de rentabilidad para DSR/PBO y la evaluación cronológica se diseñarán aparte.

Se exige una predicción de cada una de las cinco particiones esperadas. Si falta alguna probabilidad válida, la media correspondiente queda ausente; no se promedian solo las restantes. Las particiones sin ejemplos de validación también se conservan en las métricas para ambos métodos, con cero ejemplos, log-loss/AUC ausentes y estado `empty_validation`. Una partición con una única clase de entrenamiento se conserva con el modelo no estimable y la referencia disponible si hay ejemplos. La ausencia de una clase en validación impide AUC, pero no log-loss al fijar las etiquetas posibles como `[0, 1]`. Una falta de convergencia detiene el experimento y se registra como fallo; no se prueban nuevos parámetros silenciosamente.

## Métricas y puerta de capacidad predictiva

- **Log-loss:** media de `-[y*log(p) + (1-y)*log(1-p)]`. Menor es mejor. Penaliza especialmente equivocarse con mucha seguridad. Las probabilidades originales se guardan; para evitar logaritmos de cero, scikit-learn limita sus valores a la precisión de máquina de float64 al calcular la métrica.
- **AUC:** capacidad de asignar mayor probabilidad a un ejemplo positivo que a uno negativo, dando medio crédito a empates. Se calcula a partir de probabilidades, sin convertirlas en decisiones con un umbral. No mide rentabilidad.

La guía 1.B indica una AUC aproximadamente a partir de 0,54, log-loss menor que el ingenuo y mejores resultados que las sombras. En este incremento se muestran las dos primeras comparaciones, sin declarar superada la puerta completa: `skill_gate_status="pending_model_shadows"`. Las sombras del cribado univariante del 09 no son sombras de este clasificador. La prueba posterior deberá repetir el aprendizaje y la agregación bajo su referencia desplazada, con reglas fijadas antes de ejecutarla. Una AUC de 0,54 no es por sí sola una prueba de significación.

No se selecciona una configuración ganadora en función de estas métricas. La guía propone una escalera con compuestos y logística L2; aquí se establece primero la referencia L2 con todas las candidatas, de acuerdo con el plan del proyecto. Los compuestos, la selección mediante Clustered MDA con validación interna, otros modelos y SHAP siguen pendientes. El resultado de este primer modelo no justifica omitir esas comparaciones.

## Entrega y registro sencillo

`11_regresion_logistica.ipynb` muestra el diseño, recuentos, una comparación de probabilidades, log-loss/AUC y coeficientes por partición. Las funciones están en `src/tfm/logistic.py`. Se incorpora scikit-learn mediante el extra opcional `models`, en vez de mantener un optimizador propio. SciPy y las demás bibliotecas que instala son dependencias transitivas. El flujo 01–10 no necesita importar scikit-learn para funcionar.

Se guardan cuatro Parquet con sus JSON en `data/processed/`:

| Tabla | Contenido |
|---|---|
| `logistic_predictions` | Regla, partición, mes objetivo, etiqueta y probabilidades de logística/referencia, con estado del ajuste. |
| `logistic_monthly` | Una fila por regla y mes utilizable; media de las cinco probabilidades y recuento de disponibles. |
| `logistic_metrics` | Log-loss y AUC de ambos métodos, por partición y para el resumen mensual. |
| `logistic_coefficients` | Intercepto y diez coeficientes por regla y partición, con estado del ajuste. |

Antes del primer ajuste se añade un evento a `outputs/experiments/logistic_trials.jsonl`. Al terminar se añade su resultado, o el error si falla. Es un historial científico mínimo con la variante, las reglas, las entradas previstas, los costes, la versión de la biblioteca y las métricas agregadas, separado de las tablas reemplazables. No contiene firmas de archivos ni un gestor de ejecuciones. Repetir la misma variante registra otro intento, no otra configuración candidata. Las quince particiones tampoco se cuentan como quince variantes; DSR/PBO requerirán más adelante los ensayos y retornos correspondientes, con sus propios supuestos.

Regenerar entradas de 01, 02, 07 u 08, o guardar las particiones del 10, retira las cuatro tablas del 11. Repetir el 09 no las retira. El historial no se elimina. Las tablas se publican por separado: si falla la celda de guardado, se repite completa antes de utilizar las salidas. Las versiones de NumPy, pandas y scikit-learn quedan en los informes. No se guardan modelos pickle ni se incorporan datasets al repositorio.

## Comprobaciones esenciales

Se comprueba que cambiar etiquetas de validación no cambia el ajuste ni sus probabilidades; que las exclusiones temporales se mantienen y solo se usan las diez columnas explícitas; que existen cinco predicciones por ejemplo; y que el resumen, la referencia y las métricas coinciden con ejemplos manuales. El recorrido del notebook se verifica con datos sintéticos temporales, incluida la persistencia, el historial y la invalidación de salidas. Las fuentes originales y los datos desde 1990 no se usan en estas pruebas.

## Referencias

- Guía del tutor del 7 de noviembre de 2026, sublínea 1.B, páginas 2–3 y 18–19.
- López de Prado (2018), capítulos 7 y 12, para validación purgada y CPCV; la agregación mensual es una decisión explícita de este experimento.
- Ejemplo de logística de Jansen: [archivo y revisión consultados](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/11_ml_pipeline/03_logistic_classification.py). Apoyo para organizar probabilidades y métricas; no se copia su código ni su validación walk-forward. Véase `referencias_jansen.md`.
- Documentación oficial: [LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [log-loss](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html) y [AUC](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html). Consultadas el 14 de noviembre de 2026.

## Primera ejecución y verificación

El 14 de noviembre de 2026 se ejecutaron todas las celdas en un proceso limpio, utilizando únicamente las tablas locales de desarrollo y bloqueando las descargas. Convergieron los treinta ajustes sin cambiar parámetros. Se guardaron 5760 predicciones de validación, 1152 resúmenes por regla y mes (442 de momentum y 710 de reversión), 64 filas de métricas y 330 coeficientes incluyendo interceptos. Los Parquet guardados coinciden exactamente con los resultados calculados. Los 34 archivos de datos anteriores permanecieron intactos. Las nuevas salidas y el historial científico se conservan localmente, fuera de Git.

| Regla | Log-loss L2 | Log-loss ingenuo | AUC L2 | AUC ingenuo |
|---|---:|---:|---:|---:|
| Momentum | 0,678228 | 0,680904 | 0,566145 | 0,433950 |
| Reversión | 0,655320 | 0,660392 | 0,605721 | 0,473115 |

Estas métricas corresponden al resumen de cinco probabilidades por ejemplo. Ambas logísticas mejoran ligeramente la log-loss y superan la referencia de AUC de 0,54, pero no se declara superada la puerta completa: las sombras del modelo y su utilidad económica siguen pendientes. No se han modificado variables o parámetros a partir de estos resultados.

Pasan las 58 pruebas del proyecto, incluidas las cuatro comprobaciones del incremento. La regresión de particiones vacías conserva las treinta combinaciones de partición y regla incluso cuando veinte carecen de ejemplos de validación. Se revisó también el gráfico: los meses sin ejemplo utilizable se muestran como huecos, sin interpolar probabilidades, y los marcadores permiten ver las observaciones aisladas. Los notebooks se entregan con salidas y contadores de ejecución vacíos.

## Continuación del experimento

El notebook 12 aplica el [protocolo de sombras de la logística](sombras_logistica.md). Lee estas salidas sin volver a ajustar el modelo original y guarda su comparación aparte. Sus criterios se fijan después de conocer las métricas anteriores y antes de calcular las sombras. El estado pendiente de sombras en los informes originales del 11 describe su alcance; la comparación posterior pertenece a los informes del 12.
