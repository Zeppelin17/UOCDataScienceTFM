# Plan de la CLI interactiva

## Objetivo

Permitir ejecutar las tareas del TFM eligiendo opciones, sin memorizar comandos. Mantener los comandos explícitos para automatización y reproducción de experimentos.

## Estado y decisión actual

La CLI existente separa la presentación (`tfm.cli`) del flujo (`tfm.pipeline`) y de los módulos de datos. Esta estructura permite incorporar un menú sin reorganizar la lógica. El menú inicial está implementado en `tfm.menu`, utiliza la biblioteca estándar y reutiliza `run_prepare_prices`. Los comandos existentes se conservan.

## Menú inicial implementado

El bloque implementado antes del simulador contempla:

1. Abrir un menú al ejecutar `python -m tfm` en una terminal interactiva. Conservar `prepare-prices` y sus argumentos. Sin terminal interactiva, mostrar ayuda y terminar sin esperar entradas.
2. Ofrecer descargar y preparar precios, preparar una descarga existente, consultar ejecuciones, ver la configuración y salir.
3. Mostrar los snapshots locales con instrumento, periodo e identificador y permitir seleccionarlos por número. Comprobar compatibilidad con la configuración antes de procesarlos.
4. Mostrar resumen de ejecuciones con estado y rutas a resultados e informes. No elegir automáticamente la última ejecución ni reutilizarla implícitamente.
5. Validar las entradas, permitir volver al menú y manejar cancelaciones. Mostrar periodo y configuración antes de una descarga.
6. Llamar a los mismos flujos existentes, conservando sus registros y controles. Mantener las acciones de consulta como operaciones de lectura.

Usar inicialmente la biblioteca estándar de Python. Añadir solo pruebas esenciales de selección y delegación, manteniendo los tests existentes del flujo como verificación de la lógica de datos.

## Ampliaciones posteriores

Añadir opciones de anomalías, variables, entrenamiento y evaluación cuando se implementen sus respectivos módulos. Cada acción deberá disponer también de un comando explícito y utilizar el mismo flujo tanto desde el menú como desde la ejecución automatizada.

El menú facilitará seleccionar configuraciones; no introducirá ahora un editor de parámetros ni permitirá saltarse la separación entre desarrollo y evaluación final. Los controles temporales se implementarán en los módulos correspondientes.

## Ajuste de usabilidad implementado

Las acciones usan directamente la configuración activa, inicialmente `configs/data.toml`. La opción 4 la muestra sin preguntas y la opción 5 permite cambiarla explícitamente para la sesión. Una ruta inválida conserva la configuración anterior. La selección de descargas muestra periodo, fecha de descarga y número de sesiones cuando el manifiesto los incluye, con instrucciones sobre los números válidos. El resultado resume sesiones, periodo y controles, junto con las limitaciones pendientes del informe.


## Simulación implementada

La opción 6 ejecuta comprar y mantener desde una preparación seleccionada por número, usando `buy_and_hold.toml` situado junto al TOML de datos activo. La configuración de simulación es independiente de la de descarga: muestra su ruta, fechas inclusivas y coste antes de listar las preparaciones. No se realiza una descarga. La verificación completa de integridad y del periodo de desarrollo se hace en el coordinador incluso si se utiliza el comando explícito. Las preparaciones incompatibles por cobertura o periodo se omiten del selector.

El resultado muestra rentabilidad bruta/neta, capital, coste, rotación y caída máxima, además de supuestos y rutas. El historial distingue los comandos y muestra las salidas financieras. El comando reproducible es `python -m tfm simulate-buy-and-hold --config configs/buy_and_hold.toml --prepared RUTA`.


## Auditoría de calendario implementada

Opción 7: elige preparación y ejecuta `audit-prices` con `audit.toml`, sin descargas. Muestra intervalo completo, calendario, sesiones esperadas/observadas, faltas y fechas inesperadas, además de los otros campos pendientes. La opción 6 permite elegir explícitamente una auditoría compatible tras seleccionar precios, o 0 para simular sin ella con advertencia. No se utiliza automáticamente la más reciente. El historial distingue estado de ejecución y resultado de auditoría. Los comandos admiten `audit-prices --prepared RUTA` y `simulate-buy-and-hold --prepared RUTA --audit RUTA_AUDITORIA`, con sus configuraciones por defecto habituales.

## Incremento: distribuciones del emisor

Implementados `import-ssga-dividends --file ... --config configs/reconciliation.toml` y `audit-prices --reference ... --config configs/reconciliation.toml`. La opción 8 permite seleccionar una preparación y una referencia existente o importar otro Excel oficial. La opción 7 conserva el calendario y la opción 6 permite seleccionar explícitamente una auditoría v1/v2. Se muestran cobertura, concordancia y discrepancias sin atribuir aprobación a precios o ajustes. Detalles y resultados reales en [source_reconciliation.md](source_reconciliation.md).

## Incremento principal: historia mensual de Shiller

Implementados `prepare-shiller [--config configs/shiller_monthly.toml] [--file XLS | --snapshot DIRECTORIO]` y la opción 9. Sin origen explícito se descarga; el menú exige elegir D, F o un snapshot por número. Se muestran meses de historia/desarrollo y limitaciones. Las opciones previas SPY conservan numeración y se identifican como exploración anterior. Detalles en [shiller_monthly.md](shiller_monthly.md).
