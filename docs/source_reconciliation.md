# Contraste de distribuciones con State Street

> Documento del flujo anterior: sus comandos se conservan temporalmente. Las referencias a la numeración antigua del menú son históricas; el recorrido actual se describe en [cli_plan.md](cli_plan.md). Los supuestos y hallazgos científicos siguen documentados aquí hasta su consolidación.

## Alcance de este incremento

Se implementa un contraste numérico real de distribuciones monetarias de SPY contra el listado histórico de su emisor, obtenido sin usar Yahoo. Se conservan por separado dividendos de renta y ganancias de capital. **El contraste independiente de cierres de mercado y de ajustes de rentabilidad total permanece pendiente.** La coincidencia de dividendos no acreditaría esos campos.

Se verificaron las fuentes antes de elegir el adaptador:

- State Street publica el Excel `SPDR Historical Distributions XLSX`, con SPY/CUSIP 78462F103 desde marzo de 1993. Es una publicación del emisor; no se conoce toda la cadena de proveedores de Yahoo, así que no se afirma independencia demostrada de su procesamiento upstream.
- El Excel `navhist-us-en-spy.xlsx` contiene NAV, no cierres de mercado. `pdhist-us-en-spy.xlsx` contiene primas/descuentos. No son una segunda serie de cotizaciones comparable.
- Stooq devolvió una página de verificación JavaScript en lugar de un CSV; no se considera un proveedor integrado. No se intenta eludir esa verificación.
- Alpha Vantage documenta DAILY_ADJUSTED como servicio premium con API key. No se ha contratado, integrado ni supuesto acceso gratuito.

Fuentes: [distribuciones y definición de ex-date](https://www.ssga.com/us/en/intermediary/resources/documents/etf-dividend-distributions), [Excel histórico](https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx), [SPY: diferencia entre NAV y cotización](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy), [Alpha Vantage](https://www.alphavantage.co/documentation/#dailyadj). Verificadas el 17/10/2026.

## Política fijada antes del contraste

`configs/reconciliation.toml` fija la ventana de referencia, con final exclusivo, y una tolerancia absoluta de **0,0005005 USD por participación**, sin tolerancia relativa ni desplazamientos de fechas. Los eventos Yahoo preparados tienen tres decimales y el listado SSGA seis: se suma media unidad de ambas precisiones (0,0005 + 0,0000005). Esta tolerancia no explica ni corrige diferencias económicas. El protocolo versionado rechaza otros valores; revisarlo exigiría una decisión documentada, una versión nueva y conservar el resultado anterior.

La fecha utilizada es la **exdividendo**, nunca la de registro o pago. Se contrasta el importe de Yahoo con la suma publicada por SSGA de dividendo de renta, ganancias de capital a corto plazo y a largo plazo. Los tres componentes se conservan para examinar diferencias de clasificación; una diferencia no demuestra cuál de los proveedores tiene razón ni certifica que Yahoo trate todos los componentes de igual modo. No se redondean importes ni se reconstruyen ajustes. Si se detectan splits, el contraste se rechaza hasta disponer de una política que equipare sus escalas.

Se comparan **todos** los eventos de la intersección temporal mediante una unión externa. Un evento presente en una sola fuente se registra como discrepancia. No se comparan solo las fechas coincidentes ni se reduce la muestra después de observar diferencias. Las sesiones sin distribución no se contabilizan como miles de coincidencias artificiales.

Cobertura y concordancia son dimensiones distintas:

- `coverage`: `complete`, `partial` o `none`, respecto al intervalo solicitado de la preparación.
- `agreement`: `within_tolerance`, `discrepant` o `not_evaluated`.
- `status`: `failed` si hay discrepancias, incluso con cobertura parcial; `passed` solo con cobertura completa, eventos comparados y concordancia; `partial` si la cobertura es parcial y concuerda; sin eventos o solapamiento, `not_evaluated`.

La cobertura describe el listado recibido y la ventana explícita seleccionada. No es una certificación externa de que el emisor no omita ningún evento. No se usa la primera y última fecha de evento como si delimitasen todos los días cubiertos. Para detectar exportaciones truncadas, este adaptador concreto exige la primera distribución conocida de marzo de 1993 y una fecha publicada posterior o igual al final solicitado; no sirve para un fichero recortado arbitrariamente.

## Originales y protección temporal

`import-ssga-dividends` importa un fichero local elegido explícitamente. No realiza descargas ocultas. Se archiva bajo `data/raw/ssga/SPY/<snapshot_id>/`:

- `original.xlsx`: bytes originales completos, sin reescribir; puede contener fechas posteriores a 2020.
- `dividends.parquet`: exclusivamente importes de la ventana de referencia permitida por la política de desarrollo.
- `config.toml`, `validation_policy.toml` y `manifest.json`: proveedor, URL oficial, ruta del fichero importado, instante de importación, versiones, transformaciones, cobertura y SHA-256 de los archivos.

El instante registrado es el de importación, no una fecha de descarga afirmada sin evidencia. La URL es la procedencia declarada del formato: importar un fichero local y registrar su hash no autentica que esos bytes se descargaran del emisor. La ejecución real inicial sí usó la descarga HTTPS del enlace oficial. Los ficheros completos quedan en originales, excluidos de Git; no se comparten datasets sin revisar sus condiciones de uso.

Se leen fechas para identificar el instrumento y filtrar, pero **no se interpretan ni utilizan importes fuera de la ventana autorizada**. Los originales completos no alimentan los experimentos. La política se verifica antes de importar, al cargar la referencia y en la auditoría; el test de protección contiene importes intencionadamente inválidos desde 2021 para comprobar que no se interpretan. Esta protección no sustituye las futuras restricciones del entrenamiento y selección de modelos.

## CLI y menú

Descargar el Excel desde el enlace del emisor e importarlo:

```bash
python -m tfm import-ssga-dividends --file RUTA_DEL_EXCEL
```

El comando devuelve la ruta del snapshot. Seleccionar explícitamente ese directorio al contrastar:

```bash
python -m tfm audit-prices --config configs/reconciliation.toml --prepared RUTA_DE_PRECIOS_PREPARADOS --reference RUTA_DEL_SNAPSHOT_SSGA
```

En `python -m tfm`, la **opción 8** permite escoger una preparación y una referencia por número, o importar otro Excel escribiendo `I`. La opción 7 conserva la auditoría de calendario. Las configuraciones deben estar junto al TOML de datos activo. No se elige automáticamente el snapshot más reciente.

`audit-prices` sin `--reference` sigue generando la versión 1 de calendario. Con referencia genera la versión 2, `scope=calendar_and_distributions`, conserva el calendario y añade `reference_manifest.json`, `reference_dividends.parquet` y `distribution_comparison.parquet`, con valores de ambas fuentes, componentes, diferencias y resultado por evento. El XLSX completo permanece aislado en originales. El informe registra su ubicación y su huella.

Una ejecución técnicamente correcta es `completed`, aunque detecte discrepancias (`audit_result=failed`). Sin discrepancias, el resultado global sigue siendo `partial`: precios y ajustes permanecen sin evaluar. El comando devuelve 1 con discrepancias o errores técnicos; 0 significa ejecución sin discrepancias en las comprobaciones realizadas, **no certificación de todos los datos**. La pantalla muestra cobertura, concordancia y campos pendientes.

## Compatibilidad y simulación

Los informes v1 siguen siendo válidos para acreditar únicamente calendario. El simulador conserva la selección explícita por menú o `--audit`; no busca otro informe si el seleccionado falla. Para v2 comprueba huellas y vinculación a preparación/política/configuración, verifica la referencia original y reproduce tanto su normalización como el contraste y sus detalles. Alteraciones, una política distinta, discrepancias o atribuir aprobación a precios/ajustes se rechazan. No se relaja la validación utilizando solo la parte del intervalo que interesa al benchmark.

Con un informe v2 sin discrepancias, el benchmark exploratorio muestra dividendos y calendario por separado, manteniendo precios/ajustes pendientes. Sin adjuntar auditoría, continúa siendo una simulación exploratoria y no acredita los campos pendientes. No se corrigen Yahoo, la referencia ni resultados históricos.

## Resultado real inicial y trabajo pendiente

En el snapshot de Yahoo de 7.033 sesiones (29/01/1993–31/12/2020) y el Excel oficial importado el 17/10/2026 se contrastaron **113 eventos**, con fechas coincidentes. **110** concuerdan con la tolerancia fijada y **3** presentan diferencias:

| Fecha exdividendo | Yahoo (USD) | SSGA total (USD) | Diferencia absoluta |
|---|---:|---:|---:|
| 17/12/1993 | 0,317000 | 0,287239 | 0,029761 |
| 15/12/1995 | 0,382000 | 0,372000 | 0,010000 |
| 20/12/1996 | 0,367000 | 0,406810 | 0,039810 |

En 1996 SSGA desglosa 0,286810 de renta, 0,08 de ganancias a corto plazo y 0,04 a largo plazo. Su total no coincide con el evento Yahoo; no se excluyen componentes para hacerlo concordar. El calendario XNYS concuerda en 7.033 sesiones. El resultado de dividendos queda `failed`, cobertura `complete`, concordancia `discrepant`; precios y ajustes quedan `not_evaluated`.

Queda investigar las tres diferencias con evidencia adicional, obtener una serie utilizable de cierres de mercado y precisar una referencia comparable para ajustes/reinversión. Reconstruir retornos usando el propio cierre/dividendo de Yahoo sería un control interno, no una segunda fuente. No se declara cerrado el objetivo global de contraste independiente.
