# Tests

Ejecutar desde la raíz con el entorno virtual activado: `python -m pytest -q`.

`test_prices.py` simula las respuestas de Yahoo; no requiere red. Comprueba conservación de datos y parámetros, SHA-256, snapshots separados, rechazo de respuestas incompatibles o fuera del periodo, configuración inválida, errores de red y limpieza tras fallos de escritura.

La comprobación real del proveedor se realiza manualmente con el comando de descarga del README. No forma parte de los tests automáticos para evitar dependencia de disponibilidad y revisiones de Yahoo.

`test_preparation_prices.py` contiene tres tests esenciales: conservación y procedencia de los precios preparados, bloqueo de duplicados y ausentes, y rechazo de un snapshot modificado. Se priorizan estos riesgos sin añadir un test separado por cada comprobación del informe.

`test_pipeline.py` añade únicamente dos tests del flujo completo: comando satisfactorio y repetición sin red, y registro de un rechazo de calidad con salida de error. Simula el proveedor, pero ejecuta la persistencia, normalización y registro reales sobre tablas pequeñas.

`test_menu.py` cubre cinco recorridos esenciales: Shiller offline desde un original anterior, entradas ausentes y cancelaciones, SPY con descarga explícita, consultas de solo lectura con rechazo de configuración antigua, y entrada por terminal/corrección de TOML/cancelación o cierre de entrada.

`test_backtesting.py` incorpora cálculo manual con y sin coste, salida a efectivo, rechazo de integridad alterada/configuración inválida/datos reservados y un recorrido sin red de CLI y repetición. Comprueba intervalo, retraso de entrada, ausencia de dividendos duplicados, ausencia de costes de mantenimiento y caída desde el capital inicial.

`test_calendar_audit.py` comprueba cierres extraordinarios y reducidos, sesiones ausentes en los extremos y fechas inesperadas; auditoría/repetición por CLI y simulación con informe explícito; rechazo de otra preparación, cobertura parcial y discrepancias. Los contrastes numéricos de segunda fuente permanecen no evaluados.

`test_shiller_signals.py` verifica ventanas y ausencia de dependencia de datos posteriores, el recorrido CLI sin red con calentamiento visible, el bloqueo de integridad/política temporal y la limpieza de salidas parciales. No simula rentabilidades ni añade pruebas de modelos.


## Flujo simplificado en transición

`test_simple_data.py` comprueba el recorrido local con configuración única, equivalencia de tablas y señales, reutilización de originales, invalidación de señales, protección temporal y conservación de salidas ante errores. También verifica que SPY mantiene yfinance y sus opciones de descarga. No accede a la red ni altera datos del proyecto. Las pruebas científicas y de comandos anteriores siguen activas hasta retirar sus respectivos flujos; se han eliminado las pruebas exclusivas del navegador retirado y los recorridos de menús que ya no existen.
