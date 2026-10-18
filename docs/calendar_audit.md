# Auditoría del calendario de SPY

> Documento del flujo anterior: sus comandos se conservan temporalmente. Las referencias a la numeración antigua del menú son históricas; el recorrido actual se describe en [cli_plan.md](cli_plan.md). Los supuestos y hallazgos científicos siguen documentados aquí hasta su consolidación.

## Alcance y referencia

La auditoría comprueba la concordancia de las fechas con **XNYS**, calendario de referencia de sesiones regulares de renta variable estadounidense de `exchange_calendars`. No afirma reconstruir los cambios históricos del mercado primario de SPY, verificar el instante de cierre de cada cotización ni certificar sus precios. El emisor identifica actualmente el instrumento en NYSE Arca; se utiliza la referencia US explícita para sesiones diarias, con las limitaciones indicadas. La política elegida y la biblioteca no se cambian para hacer desaparecer discrepancias.

Se incluye una dependencia mantenida para evitar una lista propia de festivos. Se ha verificado con exchange_calendars 4.13.2, Python 3.14 y pandas 3.0.6. El rango se pasa explícitamente, incluyendo historia desde 1993: no se utiliza el intervalo por defecto de la biblioteca. Se guarda el listado concreto de sesiones y aperturas/cierres UTC para reconstruir la comprobación, además de versiones de calendario y tzdata.

El calendario contiene cierres extraordinarios y sesiones reducidas. Las pruebas comprueban septiembre de 2001, Sandy en 2012, el cierre del 5 de diciembre de 2018 y la sesión reducida del 24 de diciembre de 2020. Las sesiones reducidas cuentan como días válidos. La comprobación es diaria, no una auditoría de datos intradía.

## Qué intervalo se comprueba

Se usa el **intervalo solicitado** del manifiesto original, `[start, end)`, con final exclusivo como Yahoo. No se deduce el intervalo de la primera y última fila recibidas: eso ocultaría sesiones ausentes en los extremos. El informe incluye sesiones esperadas, observadas, ausentes e inesperadas, sin rellenar precios ni eliminar registros.

Solo se auditan preparaciones estructuralmente aprobadas y compatibles cuya huella se verifica. Tanto la cobertura solicitada como los datos deben permanecer dentro del desarrollo según `configs/experiment_base.toml`; se rechazan solicitudes que invadan la evaluación final, aunque no se hayan recibido filas de ese periodo.

La cobertura comienza en la fecha solicitada (actualmente 29/01/1993), no necesariamente en la fecha de lanzamiento del fondo. Que ese intervalo coincida no certifica los días anteriores a la muestra.

## Ejecución

Desde la raíz, con el entorno virtual activado:

```bash
python -m tfm audit-prices --config configs/audit.toml --prepared RUTA_DE_PRECIOS_PREPARADOS
```

En el menú, la opción 7 permite escoger una preparación por número y auditarla. `configs/audit.toml` debe estar junto al TOML de datos activo. El proceso no descarga precios ni modifica la preparación. La salida de red se limita a la instalación inicial de dependencias; la auditoría funciona sin red.

Cada ejecución crea un directorio propio con:

- `run.json`: estado técnico, fases, revisión de Git, versiones, huellas y resultado de calendario.
- `config.toml` y `validation_policy.toml`: configuración y política exactas.
- `prepared_manifest.json` y `quality_report.json`: procedencia y controles anteriores, conservados sin alteración.
- `calendar_sessions.parquet`: sesiones esperadas, aperturas/cierres UTC y marca de sesión reducida.
- `audit_report.json`: intervalo completo, vinculación a precios/manifiesto/configuración/política y estados de comprobación.

Una ejecución que detecta discrepancias puede ser `completed`, con `audit_result=failed`: se ha ejecutado bien la comprobación y ha encontrado problemas. Un error técnico deja `failed` o `interrupted`, con explicación y sin resultados parciales publicados. El comando devuelve 0 solo cuando la comprobación de calendario se supera, y 1 ante discrepancias o error técnico, con mensajes diferenciados. El historial muestra el resultado técnico y el de calendario por separado. Un resultado de calendario aprobado no significa que toda la calidad de datos esté certificada.

## Uso explícito desde el simulador

```bash
python -m tfm simulate-buy-and-hold --config configs/buy_and_hold.toml --prepared RUTA_DE_PRECIOS_PREPARADOS --audit RUTA_DE_EJECUCION_DE_AUDITORIA
```

El menú permite seleccionar una auditoría por número después de elegir los precios; nunca elige automáticamente la más reciente. Un informe de otra preparación, incompleto, alterado, con discrepancias, con política temporal distinta o de otra versión de calendario/tzdata se rechaza. Las huellas del Parquet y del manifiesto vinculan el informe a esa preparación concreta. Si se actualiza el entorno o la política, se repite la auditoría: los originales no se cambian.

La simulación copia el informe seleccionado y registra su huella. Sin auditoría, el benchmark exploratorio sigue disponible y muestra calendario pendiente. Las futuras tablas mensuales deberán exigir una comprobación de calendario aprobada para el intervalo que utilicen.

## Estados y compatibilidad

Las comprobaciones son independientes: `calendar`, `prices`, `dividends` y `adjustments`. Este incremento solo puede acreditar calendario; las demás quedan `not_evaluated`. Este era el alcance de la versión 1. La versión 2 añade distribuciones de State Street, conservando v1; véase [source_reconciliation.md](source_reconciliation.md). Cada comprobación especifica valores comparados, cobertura y tolerancias; comprobar cierres o dividendos no certificará automáticamente los ajustes de rentabilidad total.

Las nuevas preparaciones guardan estos estados en `quality_report.json`. Las anteriores siguen siendo compatibles: se interpretan como no evaluadas hasta adjuntar una auditoría. La nota genérica antigua se sustituye en la presentación por los estados separados, sin reescribir archivos históricos. Los avisos de supuestos financieros se mantienen aparte y no se duplican con los de calidad.

## Fuentes de la decisión

- Biblioteca y consultas de sesiones: https://github.com/gerrymanoim/exchange_calendars
- Reglas históricas XNYS: https://github.com/gerrymanoim/exchange_calendars/blob/master/exchange_calendars/exchange_calendar_xnys.py
- Horarios regulares y calendarios NYSE/Arca: https://www.nyse.com/trade/hours-calendars
- Instrumento, listado y distinción entre NAV y cotización: https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy

La fuente de horarios actuales ayuda a justificar la referencia regular; no certifica por sí sola todos los festivos históricos. Las reglas históricas proceden de la versión registrada de la biblioteca, cuyo resultado se presenta como concordancia con un calendario de referencia.
