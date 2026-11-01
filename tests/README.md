# Pruebas esenciales

Ejecutar `python -m pytest -q` desde la raíz con el entorno virtual activado. Las pruebas utilizan archivos temporales y proveedores simulados; no acceden a la red ni modifican datos del usuario.

- `test_shiller.py`: selección de fechas y columnas, interpretación de octubre, valores anualizados, rechazo de cobertura o valores incorrectos, política temporal y descarga HTTPS con conservación del original.
- `test_prices.py`: respuestas de Yahoo vacías, incompatibles o fuera de intervalo, y errores de red.
- `test_preparation_prices.py`: conservación de precios y eventos al normalizar, duplicados y valores ausentes sin corrección silenciosa.
- `test_shiller_signals.py`: cálculo manual de ventanas y direcciones, fechas de decisión/objetivo y ausencia de dependencia de observaciones posteriores.
- `test_simple_data.py`: recorrido completo con configuración única, equivalencia de tablas y señales, reutilización de originales, invalidación de señales, fallos de escritura y separación entre Shiller y SPY.
- `test_menu.py`: recorrido guiado de Shiller, entradas ausentes y cancelaciones, SPY con descarga explícita, consultas sin cambios, configuración antigua, errores de TOML y cierre de la entrada.

Se han retirado las pruebas exclusivas del coordinador de ejecuciones, huellas, auditorías, conciliación SSGA y simulador diario porque esas funciones ya no forman parte de la herramienta. Se conservan sus hallazgos en `docs/decisiones.md` y los archivos históricos en sus carpetas originales. Las comprobaciones científicas reutilizadas se han adaptado al flujo actual.

`test_simple_data.py` incluye tres regresiones de la refactorización: rechazo de parámetros adicionales que cambiarían el activo, rechazo del original SPY al cambiar su periodo solicitado y restauración de las salidas al fallar la sustitución de la tabla, del resumen o la retirada de señales. Los fallos de publicación se simulan con una nueva tabla y un resumen diferentes, comprobando que se recuperan exactamente los bytes anteriores.

`test_return_components.py` añade cuatro pruebas: unidades y selección mensual de RF (incluidos valores negativos y rechazo de huecos/códigos de ausencia), fórmulas calculables a mano y alineación temporal, descarga HTTPS/importación de French, y recorrido CLI/menú con invalidación de componentes al regenerar sus fuentes. No utiliza red ni datos reales.

`test_simulation.py` añade cinco pruebas esenciales: balance manual de largo/efectivo/corto con entrada y cierre, cambio de dirección y reajuste de cortos, alineación y ausencia de dependencia futura con parada por insolvencia, caída desde el capital inicial y sensibilidad sin dividendos, y publicación CLI con rechazo de configuración antigua e invalidación por las cuatro entradas.

`test_sensitivity.py` añade tres pruebas: escenarios con un único cambio y equivalencia con el simulador existente; efectos del préstamo y de los dividendos con parada ante insolvencia; y publicación CLI/menú, separación temporal, conservación de la salida ante un fallo, rechazo de configuración antigua e invalidación al regenerar entradas. Utiliza datos sintéticos y carpetas temporales.

`test_bear_filter.py` añade tres pruebas: ventana exacta de 24 meses, frontera cero, falta de historia y ausencia de información futura; conservación de las cuentas originales, paso a efectivo y balance contable; y flujo CLI/menú con los 756 meses, conservación de otras salidas e invalidaciones. El proveedor sintético de Shiller incluye ahora historia desde diciembre de 1924; se conserva la prueba de la ventana anterior como regresión.

`test_volatility.py` añade tres pruebas esenciales: balance manual de posiciones parciales largas y cortas, remuneración de efectivo, préstamo, reajustes y equivalencia con exposición completa; ventana causal de riesgo, ausencia de información futura, tope, riesgo cero y falta de historia; y flujo CLI/menú de ocho cuentas, configuración e invalidaciones. Todas trabajan sin red y con archivos temporales.

`test_diagnostics.py` añade tres pruebas esenciales: unidades, bloque de datos y exclusión de importes futuros en French/FRED; agregación mensual, muestra común, señales y contribuciones brutas de precio; y reutilización de originales sin red ni modificación, cobertura incompleta explícita y calentamiento con rezago. La extracción de fórmulas de señales se verifica también con las pruebas anteriores. No se añaden pruebas del menú para este notebook.
