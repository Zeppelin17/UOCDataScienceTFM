# Diagnóstico anual de logística y random forest

Las secciones 26–29 del notebook 14 responden al seguimiento con el tutor del 20 de noviembre de 2026: mostrar la AUC de cada periodo e investigar qué contexto acompaña a sus resultados. Se ejecutan por separado con las salidas anteriores del 14 ya guardadas. El incremento lee y contrasta resultados; no entrena, descarga, publica tablas ni cambia configuraciones.

## Contenido

- Matrices de AUC para los cuarenta años 1950–1989, ambas reglas y siete métodos: M0, L2_M1/M2/M3 y RF_M1/M2/M3. La escala fija es 0–1, centrada en 0,5; los casos no estimables permanecen en gris.
- Operaciones anuales favorables y desfavorables, para interpretar el tamaño de muestra y los años de una clase o vacíos.
- Contexto del calendario completo: meses con retorno previo de 24 meses negativo, media del indicador de volatilidad anualizada de doce retornos y distancia media al máximo de doce precios.
- Consulta de un año, con contexto del mercado completo y contexto limitado a las operaciones de cada regla, además de AUC, log-loss y estado de cálculo por método.

Cada fila de contexto corresponde al mes objetivo y conserva la característica calculada con precios hasta el mes anterior. Sus promedios anuales son descripciones retrospectivas del año, no entradas nuevas para predecirlo. La media del indicador de volatilidad difiere de calcular una volatilidad anual realizada; la distancia al máximo describe precios, no la caída de la cuenta de inversión.

## Coherencia y alcance

`src/tfm/annual_diagnostics.py` comprueba señales y referencias compartidas entre la logística y el bosque, reconstruye métricas a partir de las probabilidades y las contrasta con las tablas guardadas. Comprueba además los recuentos del calendario publicado y exige doce meses de contexto por año. Las medias del contexto operativo quedan ausentes cuando no hay operaciones; el recuento conserva cero.

Se mantienen todos los años, incluidos los no estimables. El criterio de estabilidad conserva su mayoría de 21/40. Los gráficos sirven para formular explicaciones e hipótesis descriptivas, sin seleccionar años favorables, nuevos cortes, listas o hiperparámetros. Cualquier diseño posterior basado en lo observado deberá reconocer esa exploración y seleccionar dentro del entrenamiento. No se acepta régimen por inspección visual ni se transfieren los controles de sombras entre modelos. El periodo desde 1990 continúa reservado.

No se añade una familia persistente de resultados, un historial de entrenamientos o un notebook adicional. La consolidación de cuadernos se mantiene para el final.

## Verificación con las salidas locales

Se han ejecutado las cuatro celdas nuevas desde un estado limpio, bloqueando entrenamiento, publicación y conexiones de red. Se reconstruyeron 560 métricas anuales y 14 reunidas, con las 331 operaciones de momentum y 479 de reversión conservadas. La AUC es calculable en 32 y 39 años por método, respectivamente. Se revisaron los tres gráficos y las tablas del año de ejemplo. Las tablas e historiales anteriores mantienen su contenido y las celdas nuevas se conservan sin salidas incrustadas.
