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

Añadir opciones de simulación, estrategias, variables, entrenamiento y evaluación cuando se implementen sus respectivos módulos. Cada acción deberá disponer también de un comando explícito y utilizar el mismo flujo tanto desde el menú como desde la ejecución automatizada.

El menú facilitará seleccionar configuraciones; no introducirá ahora un editor de parámetros ni permitirá saltarse la separación entre desarrollo y evaluación final. Los controles temporales se implementarán en los módulos correspondientes.
