# Guía incremental para entender el TFM

Abre [guia_del_proyecto.html](guia_del_proyecto.html) con un navegador. Puedes hacer doble clic, utilizar «Abrir con» o arrastrar el archivo a una ventana de Chrome, Safari, Firefox o Edge. No requiere activar Python, instalar bibliotecas ni iniciar un servidor. Si el editor muestra el código HTML, utiliza la opción de abrir el archivo en un navegador.

La guía contiene dieciséis puntos, desde los fundamentos hasta los notebooks 00–10, y unas 15.000 palabras de explicación. Se recomienda leer en orden la primera vez. Cada punto termina con **«Lo que tiene que estar claro al terminar este punto»**, sin preguntas de autoevaluación.

Incluye:

- Conceptos financieros y matemáticos definidos antes de utilizarlos, analogías y ejemplos numéricos.
- Explicación de las decisiones y límites del estudio, con conexiones al código por bloques.
- Desplegables de profundización, glosario y búsqueda dentro de los capítulos.
- Ejemplos modificables de capitalización, señales, tamaño por riesgo, cuentas y etiquetas, preparación causal y pruebas múltiples.
- Exploración de las quince particiones de validación, con recuentos agregados del proyecto.

Los laboratorios numéricos utilizan ejemplos ficticios identificados. Los recuentos reales son una fotografía de los datos preparados revisada el **8 de noviembre de 2026**, con el criterio y los resultados del cribado actualizados el **14 de noviembre de 2026**; el HTML no lee las tablas al abrirse ni se actualiza automáticamente. Tampoco ejecuta notebooks, escribe datos o entrena modelos.

Los enlaces externos solo se abren si los seleccionas. Los enlaces al código y documentación funcionan al conservar la guía en `docs/`, dentro del repositorio. Puedes compartir el HTML de forma independiente y seguirá conteniendo el texto y las interacciones, aunque esos enlaces relativos al repositorio necesitarán sus archivos.

El botón **«Imprimir / guardar PDF»** prepara el recorrido completo, no solo el punto visible, y abre los detalles matemáticos y de código para incluirlos. El navegador permite guardar el documento como PDF. Los controles interactivos se imprimen con el estado que tengan en ese momento.

La guía distingue lo implementado, los supuestos de simulación y las metodologías pendientes. No modifica la memoria ni sustituye las fuentes académicas que deban leerse y citarse en ella.

Se ha revisado el recorrido completo contra el código y las decisiones del proyecto, con especial atención a las fechas, las unidades, los costes, las etiquetas y las particiones de validación. Las calculadoras de cuentas se han contrastado con el motor de Python usando ejemplos ficticios.

El punto 13 utiliza BH con p ajustado < 0,10 como criterio principal y Holm al 5 % como comprobación adicional. El signo esperado y las sombras se interpretan por separado; las diez características siguen siendo candidatas.
