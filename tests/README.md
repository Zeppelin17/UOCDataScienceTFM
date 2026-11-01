# Pruebas esenciales

Ejecuta `python -m pytest -q` desde la raíz con `.venv` activado. Las pruebas utilizan archivos temporales y proveedores simulados; no acceden a la red ni modifican datos del estudiante.

Se mantienen las comprobaciones de lectores de Shiller, French y Yahoo, cobertura mensual, selección temporal, reglas calculables a mano, alineación entre decisiones y resultados y fórmulas financieras. Incluyen efectivo, cortos, dividendos, costes de negociación y préstamo, liquidación, posiciones parciales, insolvencia y ausencia de dependencia de datos posteriores. También se conservan los controles del diagnóstico de fuentes.

`test_simple_data.py` comprueba equivalencia de tablas y señales, reutilización de originales, rechazo de datos incorrectos y restauración de salidas si falla la escritura o la retirada de dependientes. `test_notebook_flow.py` ejecuta las celdas de preparación y simulación de 01–06 con fuentes sintéticas y verifica su guardado y la invalidación de los resultados al regenerar entradas. Este recorrido requiere las dependencias opcionales de notebooks; se omite si no están instaladas.

Se han retirado las pruebas exclusivas del menú, los comandos, el TOML y el antiguo coordinador auxiliar de SPY porque esas funciones se han eliminado. Las comprobaciones financieras se conservan. Las integraciones repetidas de cada comando se sustituyen por un recorrido de los notebooks. Los lectores genéricos de Yahoo siguen cubiertos y se utilizan en el diagnóstico actual. Los hallazgos previos de SPY permanecen en `docs/decisiones.md`.

`test_features.py` comprueba las diez fórmulas con un ejemplo manual, los retrasos de crédito e industrias, las unidades y el calentamiento de amplitud sin convertirlo en cero. También altera precios y contexto posteriores para verificar que no cambian filas anteriores, y rechaza huecos, duplicados y valores inválidos. Las pruebas del flujo comprueban que regenerar Shiller retira las características anteriores.

El retorno de 24 meses se contrasta exactamente con el comparador bajista en todos los meses; se comprueban sus dos extremos para el primer objetivo de 1927 y el rechazo de historia insuficiente.
