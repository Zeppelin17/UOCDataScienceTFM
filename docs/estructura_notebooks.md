# Estructura de notebooks para la entrega

Decisión del 15 de noviembre de 2026. Esta es la estructura objetivo: los siete cuadernos indicados aún no se han creado mediante consolidación. Los notebooks actuales 00–14 siguen siendo los ejecutables. Se reorganizarán cuando se estabilice el modelado, conservando cálculos, resultados y explicaciones útiles.

## Siete preguntas, siete cuadernos

Los nombres siguientes son los previstos para la entrega, no rutas de archivos que haya que ejecutar ahora.

| Notebook previsto | Pregunta y contenido | Procedencia actual |
|---|---|---|
| `01_datos_y_fuentes.ipynb` | ¿Qué datos tenemos y qué significan? Fuentes, cobertura, diagnóstico de medias frente a cierres, preparación de Shiller, RF, dividendos aproximados, crédito e industrias. Fechas, unidades y limitaciones. | 00, preparación de 01 y componentes de 02; lectura del contexto de 07. |
| `02_estrategias_de_referencia.ipynb` | ¿Cómo funcionan las reglas y contra qué compararemos el filtro? Señales, contabilidad, comprar y mantener, momentum, reversión, costes, sensibilidad, veto bajista y exposición por volatilidad. | Señales de 01 y simulaciones de 03–06. |
| `03_caracteristicas_y_etiquetas.ipynb` | ¿Qué puede conocer el modelo y qué debe aprender? Fórmulas, disponibilidad, hipótesis, calentamiento, transformaciones causales, muestra común y etiquetas. | 07–08 y explicación de la preparación compartida por 09, 10 y 14. |
| `04_analisis_exploratorio.ipynb` | ¿Qué asociaciones observamos durante el desarrollo? Regresiones HAC, BH al 10 %, terciles, subperiodos y sombras descriptivas. Resultados favorables y desfavorables. | 09. |
| `05_modelado_y_validacion_temporal.ipynb` | ¿Qué predicen los candidatos fuera de su entrenamiento? Calendarios CPCV y walk-forward, purga, referencias, escalera de modelos, comparación M0–M3 y métricas predictivas. | 10, 11, 14 y sus próximas ampliaciones. |
| `06_validacion_del_filtro.ipynb` | ¿Resiste la aportación del filtro las comprobaciones del desarrollo? Selección interna Clustered MDA, sombras del recorrido correspondiente, estabilidad, evaluación económica continua, comparadores, controles de sobreajuste e interpretación cuando proceda. | 12–13 y ampliaciones pendientes. |
| `07_evaluacion_final.ipynb` | ¿Se mantienen los resultados desde 1990? Evaluación con el procedimiento congelado, comparación de referencias, subperiodos, comprobación del mapa de regímenes y conclusiones. | Pendiente. |

El diagnóstico de Yahoo se integra como contraste de fuentes en el primer cuaderno; no se convierte en una segunda serie principal ni se empalma con Shiller. Su descarga seguirá siendo complementaria y no necesaria para entrenar el filtro.

## Orden de lectura y dependencias

La lectura sigue 01 → 07. Cada notebook comienza indicando su pregunta, entradas necesarias, salidas y limitaciones, y termina con lo que debe quedar claro y el siguiente paso.

Las dependencias de cálculo siguen las tablas publicadas y los módulos, no variables que permanezcan en el kernel de otro notebook:

- El 01 prepara fuentes y componentes; el 02 construye señales y comparadores a partir de esas entradas.
- El 03 prepara las características y etiquetas, reutilizando las señales y el motor financiero. No necesita ejecutar todas las simulaciones de sensibilidad del 02.
- El 04 describe el desarrollo. Sus asociaciones y su lista de resultados significativos no alimentan automáticamente el modelado del 05.
- El 05 usa la muestra y los calendarios declarados. El 06 reutiliza ese diseño para comprobar los candidatos; no mueve sus fronteras según los resultados.
- Las salidas de desarrollo de 05/06 determinan el procedimiento que recibirá el 07. Los resultados de 07 no se utilizan para modificarlo.

Cada cuaderno deberá ejecutarse en un kernel nuevo con sus entradas publicadas. Las celdas emplearán funciones de `src/tfm`, con listas explícitas de predictores, parámetros visibles y periodos fijados. Se mantiene la ausencia de CLI y ficheros de configuración.

## Separación entre modelado, validación y evaluación final

Agrupar archivos no cambia la metodología. La selección de variables, hiperparámetros o umbrales seguirá limitada al entrenamiento de cada partición, con separación interna cuando corresponda. Una variante que incluya Clustered MDA debe evaluar el recorrido completo, sin seleccionar una vez con todo el desarrollo y reutilizar esa selección en sus pruebas.

El 05 establece y compara los candidatos predictivos. El 06 evalúa su selección, robustez y utilidad dentro de 1927–1989. Puede mostrar sus etapas en secciones, invocando los mismos módulos; no duplica el código de ajuste. Las comparaciones predictivas y económicas corresponden a la variante efectivamente comprobada, no se transfieren desde un modelo anterior.

La evaluación económica del desarrollo queda en 06 porque la guía la exige para aceptar un régimen. SHAP se muestra como mapa de regímenes aceptados una vez comprobados los criterios correspondientes. Si no hay regímenes aceptados, se documenta ese resultado; no se fuerza un mapa favorable. Los controles DSR/PBO se calculan cuando existan las variantes y sus retornos necesarios, conservando sus supuestos y limitaciones.

El 07 queda separado para ejecutar la evaluación desde 1990 una vez fijados variables, modelos, reglas de selección, umbrales y reentrenamiento. Mantendrá la política anual acordada y la fecha de corte predefinida de 2026. Se reportarán también 1990–2007 y 2008–corte. El reentrenamiento programado no autoriza a rediseñar el método a partir de esos resultados. La exposición previa a datos posteriores y las limitaciones de Shiller seguirán declaradas.

## Cómo desarrollaremos a partir de ahora

La unidad de incremento y commit puede ser una sección de un notebook; no necesita convertirse en otro archivo.

El notebook `14_referencia_walk_forward.ipynb` se amplía para comparar M1 y M2 con las mismas fechas y parámetros. M3 se incorpora en otra sección del mismo recorrido y las retiradas individuales seguirán esa organización, conservando la identificación y los resultados de cada variante. Este contenido se integrará más adelante en el cuaderno final 05. No se abrirá un notebook 15 solo para añadir M2.

Las nuevas sombras y comprobaciones se incorporarán al bloque de validación. Durante la transición, se elegirá el cuaderno existente que corresponda y se ajustará su título si hace falta; una operación nueva debe quedar correctamente identificada, aunque comparta cuaderno con otra anterior. Los experimentos extensos tendrán una sección de cálculo explícita y una lectura de sus resultados ya guardados, cuando se implemente esa organización. Consultar una tabla o un gráfico no deberá obligar a recalcular todas las sombras.

Las explicaciones actuales se conservarán cuando aporten valor. La consolidación eliminará introducciones repetidas, lecturas redundantes y tablas duplicadas; no eliminará supuestos, resultados negativos o limitaciones para reducir artificialmente la extensión. Tampoco incluirá todos los gráficos de diagnóstico en el recorrido principal si una explicación o tabla resumida basta.

## Consolidación y comprobación

La reorganización se hará por bloques pequeños y en commits separados. Antes de retirar un notebook integrado se comprobarán, con las mismas entradas, sus tablas, métricas y supuestos; se actualizarán enlaces y pruebas de recorrido. Se mantendrán las pruebas de lógica útiles, adaptando las de notebooks al nuevo recorrido sin crear copias redundantes.

Los nombres de las tablas no tienen que coincidir con la nueva numeración de los cuadernos. Se conservarán cuando representen el mismo resultado y se ajustarán los mensajes de ayuda y las dependencias de preparación. Los historiales y las variantes científicas se conservan; juntar celdas no crea experimentos nuevos ni borra intentos anteriores.

Tras verificar la equivalencia, los cuadernos absorbidos se retirarán del recorrido activo. Su versión anterior permanecerá en Git, sin mantener una segunda colección obligatoria de notebooks de archivo. La entrega tendrá siete entradas principales y el código reutilizable seguirá en `src/tfm`.

Esta decisión organiza la entrega; no consolida archivos todavía, cambia cálculos, reejecuta modelos ni modifica la memoria. El protocolo científico de M0–M3 continúa en [validacion_walk_forward.md](validacion_walk_forward.md).
