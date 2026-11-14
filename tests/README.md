# Pruebas esenciales

Ejecuta `python -m pytest -q` desde la raíz con `.venv` activado. Las pruebas utilizan archivos temporales y proveedores simulados; no acceden a la red ni modifican datos del estudiante.

Se mantienen las comprobaciones de lectores de Shiller, French y Yahoo, cobertura mensual, selección temporal, reglas calculables a mano, alineación entre decisiones y resultados y fórmulas financieras. Incluyen efectivo, cortos, dividendos, costes de negociación y préstamo, liquidación, posiciones parciales, insolvencia y ausencia de dependencia de datos posteriores. También se conservan los controles del diagnóstico de fuentes.

`test_simple_data.py` comprueba equivalencia de tablas y señales, reutilización de originales, rechazo de datos incorrectos y restauración de salidas si falla la escritura o la retirada de dependientes. `test_notebook_flow.py` ejecuta las celdas de preparación y simulación de 01–06 con fuentes sintéticas y verifica su guardado y la invalidación de los resultados al regenerar entradas. Este recorrido requiere las dependencias opcionales de notebooks; se omite si no están instaladas.

Se han retirado las pruebas exclusivas del menú, los comandos, el TOML y el antiguo coordinador auxiliar de SPY porque esas funciones se han eliminado. Las comprobaciones financieras se conservan. Las integraciones repetidas de cada comando se sustituyen por un recorrido de los notebooks. Los lectores genéricos de Yahoo siguen cubiertos y se utilizan en el diagnóstico actual. Los hallazgos previos de SPY permanecen en `docs/decisiones.md`.

`test_features.py` comprueba las diez fórmulas con un ejemplo manual, los retrasos de crédito e industrias, las unidades y el calentamiento de amplitud sin convertirlo en cero. También altera precios y contexto posteriores para verificar que no cambian filas anteriores, y rechaza huecos, duplicados y valores inválidos. Las pruebas del flujo comprueban que regenerar Shiller retira las características anteriores.

El retorno de 24 meses se contrasta exactamente con el comparador bajista en todos los meses; se comprueban sus dos extremos para el primer objetivo de 1927 y el rechazo de historia insuficiente.

`test_labels.py` añade tres comprobaciones importantes: cuentas manuales y sensibilidad (incluido empate y ausencia de señal), independencia de cada operación respecto a otros meses y rechazo de entradas inválidas, y ejecución del notebook con persistencia e invalidaciones. La sensibilidad conserva dividendos y préstamo. Se comprueba que el lector rechaza las características antiguas y que los meses en efectivo no pasan a ser negativos. Las pruebas financieras existentes verifican también el comportamiento habitual del motor, que conserva posiciones.

`test_screening.py` cubre: preparación causal con límites y z-score calculables a mano, retardos de fuentes, calentamiento y empates; HAC contrastado con un sandwich matricial calculado mediante aritmética racional, BH/Holm sobre veinte pruebas, límite estricto de BH en 0,10, empates, signo y sombras separados del criterio principal; y recorrido del notebook 09 sin red, con respuesta de la regla continua, persistencia de las cinco tablas e invalidación al regenerar entradas. No se instalan SciPy ni statsmodels: el módulo usa NumPy, ya presente y declarado como dependencia directa.

La regresión de sombras parciales comprueba un desplazamiento con 19 de las 20 relaciones estimables: conserva sus diagnósticos, deja ausente el máximo y desactiva la comparación completa, manteniendo BH, Holm y todas las filas de sombras.

`test_validation.py` añade dos comprobaciones: calendario fijo de seis bloques y quince parejas, fronteras inclusivas de etiqueta, fusión de bloques adyacentes y embargo de seis meses sin duplicar la purga; y ejemplos por regla, horizonte y alineación, clases únicas sin mover fechas, recorrido del notebook 10 sin red, persistencia e invalidación. Guardar resultados del cribado conserva las particiones.
