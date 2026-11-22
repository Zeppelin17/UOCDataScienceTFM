# Formas aprendidas por los modelos M1

Comparamos cómo el retorno del último mes y el momentum 12–1 mueven la puntuación de la logística, el bosque y boosting. Se aplica el mismo diagnóstico a momentum y reversión. La pregunta es si aparece una forma distinta de una recta con suficiente respaldo para estudiarla mediante EBM. El diseño es exploratorio y se fija tras conocer la comparación predictiva de los modelos.

## Fechas, tramos y recuentos

- Reproducimos los ajustes M1 disponibles al comienzo de 1959, 1969, 1979 y 1989, el último año de cada década de prueba. Para cada año se conserva la ventana expansiva hasta noviembre del año anterior. Las probabilidades de sus señales de prueba se contrastan con las guardadas previamente.
- Para describir cada modelo utilizamos las señales activas de los últimos 120 meses de su calendario de entrenamiento. Así vemos qué aprende con la historia acumulada en situaciones observadas recientemente. Los cuatro periodos que aportan señales al gráfico son consecutivos y los entrenamientos comparten historia.
- Cada variable se divide en cuatro tramos mediante los percentiles 10, 30, 50, 70 y 90. Los cortes salen de los meses utilizables de al menos una regla en el primer entrenamiento. Cada mes cuenta una vez para estimar esos cortes. Se mantienen iguales para las dos reglas, años y modelos. Cada tramo necesita ocho señales como mínimo. Los recuentos se muestran en las figuras y los tramos con poco respaldo aparecen en gris.

## Cómo se calcula cada curva

Para cada señal que cae en un tramo, calculamos dos puntuaciones. Ponemos la variable examinada primero en el extremo inferior del tramo y después en el superior. La otra variable conserva su valor observado. Promediamos las diferencias y encadenamos los cambios, con cero en el corte del percentil 50. La curva se interrumpe si falta un tramo entre un punto y ese centro. Las líneas entre cortes ayudan a leer los cambios acumulados en los intervalos estudiados.

Es una adaptación descriptiva de los efectos locales acumulados (ALE), de Apley y Zhu, con cortes comunes, mínimo de señales y centro fijo. Se usa la puntuación previa a la sigmoide. En el bosque se calcula el logit de su probabilidad, acotada entre una millonésima y uno menos una millonésima. La logística ofrece una recta de referencia bajo esta escala. [Apley y Zhu, 2020](https://doi.org/10.1111/rssb.12377)

Buscamos cambios de pendiente parecidos en varios ajustes y en tramos con señales suficientes. Las curvas son descripciones de lo que aprendieron los modelos. Los recuentos informan de la cobertura y los ajustes comparten parte de su historia. La evaluación de un eventual EBM requeriría su propio recorrido temporal. Se mantiene reservado el periodo desde 1990.

## Qué se observa en el desarrollo

En reversión, la caída más pronunciada de la puntuación en el bosque y boosting se repite en las cuatro fechas en el tramo del retorno del último mes de aproximadamente 0,11 a 0,40 en escala normalizada. El tramo contiene 26, 27, 16 y 19 señales, respectivamente. En momentum, la puntuación de ambos modelos sube mucho en ese mismo tramo, que contiene 16, 23, 8 y 15 señales. La pendiente de la logística es constante dentro de cada ajuste.

El cambio de pendiente repetido da una hipótesis concreta para un EBM aditivo con las dos entradas de M1. En reversión, el retorno mensual interviene directamente en la dirección de la operación, circunstancia que deberá tenerse presente al interpretar una posible curva. El tramo más bajo de momentum 12–1 en la regla de momentum queda vacío en las cuatro fechas. Las curvas solo describen las señales activas de la muestra.

Se reprodujeron 24 ajustes y se verificaron las probabilidades guardadas para 90 señales en los tres modelos, con tolerancia absoluta de 10⁻¹². El diagnóstico se ejecuta en memoria y usa las salidas de las secciones 32–34. Los historiales y las tablas guardadas se conservaron durante la comprobación.
