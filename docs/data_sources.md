# Fuente inicial: precios diarios de SPY

## Decisión y alcance

Proveedor propuesto: Yahoo Finance, mediante yfinance cuando se implemente el adaptador. Instrumento: SPY, ETF que sigue el S&P 500. La guía del TFM propone esta combinación. SPY es un instrumento invertible con gastos y diferencias de seguimiento respecto al índice; sus retornos no deben presentarse como idénticos a los del índice.

El emisor indica lanzamiento y cotización el 22/01/1993. La consulta efectuada a Yahoo el 03/10/2026 devuelve la primera sesión el 29/01/1993. No se reconstruirá ni inventará la semana anterior. SPY no permite una muestra desde 1990; la primera señal mensual dependerá además de la historia previa requerida por cada regla.

## Comprobación realizada

Consulta directa al endpoint chart de Yahoo, con intervalo diario y eventos de dividendos y splits, limitada al bloque de desarrollo:

- Inicio solicitado: 01/01/1993.
- Fin exclusivo solicitado: 01/01/2021.
- Filas devueltas: 7.033.
- Primera sesión: 29/01/1993.
- Última sesión: 31/12/2020.
- Campos de cotización: open, high, low, close, volume.
- Cierre ajustado: presente.
- Eventos de dividendos: 113.

Es una comprobación de disponibilidad y estructura, no una auditoría de exactitud o calendario completo. No se ha persistido esa respuesta ni instalado yfinance en este incremento. El adaptador deberá repetir y registrar estos controles con su versión concreta de yfinance.

## Parámetros explícitos

`configs/data.toml` solicita SPY desde 29/01/1993 hasta 01/01/2021 exclusivo. La documentación de yfinance define inicio inclusivo y fin exclusivo. Así se incluye 31/12/2020 sin solicitar sesiones del periodo final.

- `auto_adjust=false`: conservar OHLC y cierre ajustado por separado.
- `back_adjust=false`: no activar una transformación adicional.
- `actions=true`: conservar eventos de dividendos y splits.
- `repair=false`: no modificar silenciosamente valores mediante reparación automática.
- `keepna=true`: mantener valores ausentes para que los controles de calidad los detecten.
- `rounding=false`: conservar precisión devuelta.
- `prepost=false`: sesiones regulares.
- `ignore_tz=true`: las fechas diarias se tratarán como etiquetas de sesión, no como instantes de decisión o disponibilidad.
- `threads=false`, `multi_level_index=false`: salida sencilla para un solo instrumento.

El adaptador validará columnas y tipos de la respuesta. Los defaults de la biblioteca no deberán determinar el comportamiento del proyecto.

## Interpretación y ajustes

OHLC significa apertura, máximo, mínimo y cierre. El volumen representa actividad de negociación. Un evento de dividendo no es por sí solo su fecha de pago ni garantiza disponibilidad antes del momento de decisión.

`auto_adjust=false` no garantiza precios completamente originales o sin ajustes: la serie de Yahoo puede incorporar ajustes por splits. El cierre ajustado refleja ajustes históricos del proveedor, incluidos dividendos. Se conservarán ambos y los eventos, sin mezclar escalas.

No sumar dividendos de nuevo a retornos calculados a partir del cierre ajustado. La política de señales, precios de ejecución y dividendos de la simulación se fijará en el protocolo financiero antes de calcular resultados.

La descarga actual reconstruye historia según la versión vigente del proveedor. Guardarla permite reproducir nuestra investigación, pero no convierte los ajustes retrospectivos en snapshots point-in-time. Esta limitación deberá evaluarse según la variable calculada; no implica que todo retorno histórico esté necesariamente contaminado.

## Persistencia prevista

Conservar respuesta del adaptador sin transformaciones propias, parámetros, fecha UTC de descarga, versión de yfinance, identificador de snapshot y SHA-256. Esta copia será original respecto a nuestra descarga, no una captura del mercado realizada en 1993.

No sobrescribir snapshots. Los datos preparados apuntarán al snapshot de procedencia. Los ficheros de datos permanecen excluidos de Git.

## Uso y limitaciones

El proyecto yfinance se presenta como herramienta abierta para investigación y educación, sin afiliación a Yahoo, y advierte que los datos de Yahoo Finance están destinados a uso personal. La licencia del código de yfinance no concede derechos de redistribución de los datos. Se revisarán las condiciones aplicables antes de compartir datasets; el repositorio compartirá código y documentación, no asumirá una licencia abierta para los datos.

Otras limitaciones: posibles revisiones, interrupciones, límites de acceso, ausencia de garantías institucionales de calidad y cobertura desde 1993. No sustituir SPY por el índice ni mezclar proveedores sin documentar sus diferencias.

## Verificación pendiente

- Contrastar una selección de cierres y dividendos hasta 2020 con una segunda fuente, indicando si ofrece precio de mercado, NAV o cierre ajustado. No comparar cantidades de naturaleza distinta.
- Comprobar sesiones ausentes con un calendario adecuado.
- Validar campos, duplicados, valores ausentes y coherencia de ajustes sobre la descarga persistida.
- Fijar política de dividendos, ejecución y cortos antes del simulador.

El contraste numérico independiente no se ha completado: la fuente queda propuesta, no certificada. Si no se logra un contraste adecuado, registrar la limitación antes de usarla como base de resultados finales.

## Fuentes consultadas (03/10/2026)

- Emisor de SPY: https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy
- API de descarga: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- Repositorio y aviso de uso: https://github.com/ranaroussi/yfinance
- Endpoint consultado: https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=725846400&period2=1609459200&interval=1d&events=div%2Csplits
