# Referencias de Jansen para los próximos incrementos

Revisión: 7 de noviembre de 2026. Estado: fuentes consultadas y usos previstos. El notebook 08 aplica la idea de horizonte fijo y señal más resultado futuro mediante implementación propia; no se ha copiado código del repositorio.

Repositorio de la tercera edición: https://github.com/stefan-jansen/machine-learning-for-trading

Revisión consultada: `91c903e71c1d0f1b9015f18551fadbb60bcad132`. Los enlaces fijan esa revisión para que la referencia no cambie con la rama principal. Se inspeccionaron los scripts Python que acompañan a los notebooks y la documentación de datos; no se ejecutaron los ejemplos ni se instalaron sus bibliotecas.

## Qué aprovecharemos

| Recurso | Utilidad prevista | Adaptación necesaria |
|---|---|---|
| [Etiquetas y meta-labeling](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/07_defining_the_learning_task/03_label_methods.py) | Construcción del retorno futuro, alineación temporal, horizonte fijo e ilustración de meta-etiquetas. | Adaptar a un mes calendario y a nuestras dos reglas. La ilustración de precio no incorpora nuestra contabilidad de dividendos, RF, préstamo y negociación. |
| [Preprocesamiento](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/07_defining_the_learning_task/02_preprocessing_pipeline.py) | Patrón de ajuste sobre entrenamiento y transformación de otras particiones; límites de extremos y escalado. | El ejemplo no equivale por sí solo a la transformación expansiva causal de la guía. No trasladar su imputación a las ausencias de calentamiento. |
| [Selección y redundancia](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/08_financial_features/05_feature_selection.py) | Organización del cribado, correlaciones, agrupación, inferencia HAC y visualización de resultados. | Su IC principal es transversal sobre un panel de ETF. Nuestro cribado es temporal sobre el retorno de cada anomalía. Su importancia individual no sustituye al Clustered MDA fuera de muestra. |
| [Pruebas múltiples](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/07_defining_the_learning_task/07_multiple_testing.py) | Ejemplos de Benjamini–Hochberg, DSR y PBO. | BH no es BHY. Fijar la corrección y la familia de pruebas antes del cribado; adaptar frecuencias y ensayos reales, sin trasladar resultados simulados. |
| [Comprobaciones de alineación](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/07_defining_the_learning_task/08_causal_sanity_checks.py) | Placebos de tiempo y comprobaciones de plausibilidad como referencias de diseño. | La permutación transversal por bloques revisada no es la sombra circular mensual de la guía. Debe implementarse la referencia nula apropiada para una única serie. |
| [Logística](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/11_ml_pipeline/03_logistic_classification.py) | Separación por particiones, escalado aprendido en entrenamiento, probabilidades, AUC y log-loss. | El ejemplo emplea walk-forward; nuestro descubrimiento usa CPCV y la evaluación posterior walk-forward. No copiar su configuración, cachés o ventanas diarias. |
| [Selección y evaluación anidadas](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/11_ml_pipeline/04_nested_cv_hpo.py) | Distinción entre seleccionar configuraciones y estimar su capacidad fuera de muestra. | Adaptar al protocolo pequeño del TFM y preservar la separación entre selección y evaluación. |
| [Sobreajuste de estrategias](https://github.com/stefan-jansen/machine-learning-for-trading/blob/91c903e71c1d0f1b9015f18551fadbb60bcad132/16_strategy_simulation/12_dsr_validation.py) | Ejemplos de DSR y evaluación combinatoria de estabilidad de la selección. | Aplicar a los retornos y variantes efectivamente evaluados. Verificar supuestos y unidades mensuales antes de reutilizar fórmulas. |

La guía del 7 de noviembre indica que el índice del repositorio no incluye meta-labeling. La revisión consultada sí contiene una sección ilustrativa en `03_label_methods.py`. Ese ejemplo también contempla horizonte fijo para decisiones mensuales. Es apoyo para nuestra elección, no una implementación completa del filtro o una prueba de su rentabilidad.

## Criterios de reutilización

Se adaptarán piezas pequeñas a los notebooks y módulos existentes. Para cada uso se distinguirá entre inspiración metodológica, adaptación de una fórmula e incorporación de código. Los bloques adaptados identificarán el archivo y revisión de origen, los cambios relevantes y la atribución correspondiente. No se incorporarán bibliotecas o infraestructura del repositorio por el solo hecho de que los ejemplos las utilicen.

Las reglas y periodos de la guía del tutor prevalecen sobre los ejemplos: desarrollo mensual 1927–1989, CPCV en descubrimiento, evaluación posterior walk-forward, Clustered MDA antes de SHAP y controles de pruebas múltiples y sobreajuste. Las ventanas de 21 o 252 sesiones no se convertirán en 21 o 252 filas mensuales.

El CSV del S&P 500 incluido comienza en enero de 1980, la descarga macro consultada está configurada desde 2000 y el universo de ETF desde 2006. Esos datos no sustituyen la cobertura larga requerida. Las fuentes ya utilizadas por el TFM se mantienen. Los scripts de descarga de French y ALFRED son referencias de acceso, no garantías de cobertura o versiones históricas para todas las series.

## Etiquetado acordado y cribado pendiente

Se trabajará con horizonte fijo de un mes. No se utilizarán barreras de beneficio o pérdida intramensuales: con esa frecuencia y horizonte no se observan puntos intermedios antes del vencimiento, y los promedios no reconstruyen la trayectoria del mes. El meta-modelo seguirá aceptando o rechazando la dirección de la regla original.

El criterio central y la sensibilidad están definidos en `docs/etiquetado.md` e implementados en el notebook 08. Se compara la operación aislada neta frente al efectivo; la sensibilidad elimina solo la negociación de la etiqueta. Los costes de una operación aislada no coinciden necesariamente con los de una estrategia que conserva posiciones. El cribado está implementado en el notebook 09 y `src/tfm/screening.py`, siguiendo [hipotesis_y_cribado.md](hipotesis_y_cribado.md), que conserva las hipótesis iniciales y documenta las revisiones posteriores del criterio de significación. Se aprovecha la organización de Jansen, no su IC transversal ni su permutación entre activos. OLS/Newey–West, BH y las sombras mensuales son implementaciones propias con las referencias metodológicas indicadas en el protocolo.

## Uso en la memoria y bibliografía

La memoria ya contiene `bib:jansen2026` para el libro. Esa entrada se conservará y se ampliarán los apartados consultados cuando se utilicen otros capítulos, verificando la paginación de la edición local. No se duplicará el libro por cada notebook.

El código del repositorio tendrá una referencia distinta. Esta entrada queda preparada para añadirla al citar su uso en la memoria; no se ha insertado aún en el `.tex`:

```latex
\item \label{bib:jansenrepo2026}
Jansen, Stefan.
\textit{Machine Learning for Trading, 3rd Edition: repositorio de código}.
GitHub, s. f.
Revisión consultada: \texttt{91c903e71c1d0f1b9015f18551fadbb60bcad132}.
\href{https://github.com/stefan-jansen/machine-learning-for-trading/tree/91c903e71c1d0f1b9015f18551fadbb60bcad132}{Repositorio de la tercera edición en la revisión consultada}.
Fecha de consulta: 7 de noviembre de 2026.
```

Cada cita identificará también el capítulo o ejemplo correspondiente. La referencia al repositorio no sustituye las referencias originales de López de Prado, Newey–West, Benjamini–Hochberg, DSR, PBO u otras metodologías cuando se expliquen. Se añadirán esas fuentes primarias al redactar y utilizar cada procedimiento.
