# CLI guiada del TFM

## Recorrido actual

Ejecutar `python -m tfm` abre el menú en una terminal. Todas las tareas actuales utilizan `configs/estudio.toml` y llaman a las mismas funciones que los comandos `prepare-data` y `calculate-signals`.

1. **Preparar datos de Shiller.** Explica fuente y ventana histórica. Reutiliza el original de trabajo; si falta, permite descargar, importar un XLS o seleccionar un original anterior por número y fecha legible. Genera `data/processed/shiller_monthly.parquet` y retira las señales del flujo nuevo cuando termina correctamente.
2. **Calcular señales.** Explica momentum y reversión, utiliza la tabla mensual y genera `shiller_signals.parquet`. No descarga datos ni simula rentabilidades. Expone el calentamiento y la diferencia entre señal ausente y efectivo.
3. **Consultar datos y señales.** Muestra disponibilidad, filas y pasos pendientes. Permite ver resúmenes y las primeras cinco filas de cada tabla sin modificar archivos. Rechaza resultados con configuración diferente o entradas incompletas. El comando `status` ofrece el resumen sin interacción.
4. **Trabajar con SPY.** Identifica el ETF y Yahoo Finance, periodo diario con final exclusivo y carácter separado de Shiller. Permite reutilizar, importar o descargar el original de Yahoo. No mezcla series ni ejecuta el simulador anterior.
5. **Ver configuración.** Presenta periodos, reglas, fuente y carpeta del proyecto con explicaciones. No cambia parámetros. La configuración se vuelve a leer antes de cada tarea.

## Navegación

Se elige por número; 0 vuelve o sale. Una selección cancelada vuelve directamente. Los resultados y errores se mantienen hasta Intro. Ctrl+C cancela; Ctrl+D sale, también desde las consultas. Un error de configuración indica el archivo y permite reintentar después de corregirlo. Una entrada incorrecta no inicia descargas ni procesos.

La pantalla se limpia únicamente en terminales compatibles. No hay dependencias adicionales, explorador de ejecuciones, identificadores largos en las listas ni integración con Finder u otro gestor de archivos. Las tablas se muestran en la terminal y permanecen en sus rutas fijas para consultar con un visor externo si se desea.

## Transición

Se han retirado `run_browser.py` y sus pruebas, porque su navegación y apertura de carpetas desaparecen. Las pruebas del menú anterior se han sustituido por recorridos del menú guiado; las comprobaciones científicas y las pruebas de los comandos anteriores se conservan. Los comandos de auditoría y simulación siguen disponibles temporalmente hasta el tercer incremento, pero no aparecen en el menú. Sus funciones de presentación se conservan provisionalmente al final de `menu.py`.

No se borran originales, informes ni resultados históricos. La limpieza posterior consolidará la documentación y eliminará módulos y configuraciones del flujo retirado. Las etapas de variables, modelos y evaluación se añadirán cuando estén implementadas.
