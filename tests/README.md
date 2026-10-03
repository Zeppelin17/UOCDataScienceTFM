# Tests

Ejecutar desde la raíz con el entorno virtual activado: `python -m pytest -q`.

`test_prices.py` simula las respuestas de Yahoo; no requiere red. Comprueba conservación de datos y parámetros, SHA-256, snapshots separados, rechazo de respuestas incompatibles o fuera del periodo, configuración inválida, errores de red y limpieza tras fallos de escritura.

La comprobación real del proveedor se realiza manualmente con el comando de descarga del README. No forma parte de los tests automáticos para evitar dependencia de disponibilidad y revisiones de Yahoo.

`test_preparation_prices.py` contiene tres tests esenciales: conservación y procedencia de los precios preparados, bloqueo de duplicados y ausentes, y rechazo de un snapshot modificado. Se priorizan estos riesgos sin añadir un test separado por cada comprobación del informe.
