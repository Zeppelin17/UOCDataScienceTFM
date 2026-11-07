# Cuadernos del TFM

La entrega se ejecuta en notebooks. No hay menú de terminal ni ficheros de configuración. Los periodos, fuentes y supuestos están fijados en los lectores o visibles en las celdas; los cálculos reutilizables pertenecen a `src/tfm`.

Selecciona el Python de `.venv` en tu editor Jupyter, reinicia el kernel y ejecuta en orden. El directorio de trabajo debe ser la raíz del proyecto o `notebooks/`. Si faltan ipykernel o matplotlib, el extra `python -m pip install -e ".[notebooks]"` los incorpora; no hace falta registrar un kernel global si el editor reconoce el entorno.

## Recorrido

1. `01_datos_y_senales.ipynb` prepara Shiller y explica P, D y las dos reglas. Reutiliza `data/raw/shiller.xls`; si falta, descarga la fuente oficial. Permite indicar un XLS local. Guarda 781 meses de observaciones y 756 señales objetivo de 1927–1989.
2. `02_componentes_de_rentabilidad.ipynb` necesita el 01. Descarga o reutiliza el ZIP de French y convierte RF de porcentaje a decimal una sola vez. Explica precio, dividendo aproximado y RF por separado.
3. `03_estrategias_basicas.ipynb` simula tres cuentas, explica el balance de un mes y muestra capital, caídas y métricas.
4. `04_sensibilidad.ipynb` cambia un supuesto cada vez: negociación, préstamo o dividendos. Con el escenario central hay siete casos y 21 resúmenes. No selecciona el más rentable.
5. `05_filtro_bajista.ipynb` compara las reglas originales y filtradas junto a comprar y mantener. Utiliza el signo de la variación de precio de 24 meses, como adaptación declarada del indicador de Daniel y Moskowitz.
6. `06_ajuste_volatilidad.ipynb` compara ocho cuentas, incluyendo comprar y mantener escalado como control. Estima riesgo con 12 variaciones anteriores, objetivo anual 12 % y exposición máxima 100 %. No combina escalado y veto bajista ni optimiza sus parámetros.

7. `07_caracteristicas.ipynb` requiere solo Shiller preparado en el 01 y reutiliza o descarga industrias y crédito. Explica diez variables y sus fechas de fuente, conserva los 756 meses y marca las 749 filas completas. No utiliza Yahoo ni entrena modelos. Las fórmulas y supuestos están en `docs/caracteristicas.md`.

8. `08_etiquetas.ipynb` necesita las tablas de 01, 02 y 07. Explica la operación aislada neta frente al efectivo y compara la etiqueta central con una sensibilidad sin negociación. Conserva los meses sin señal con etiqueta ausente. Guarda `labelled_signals.parquet` y su JSON; no descarga fuentes ni entrena modelos.

Los cuadernos 03–06 requieren las tablas de 01 y 02 y se pueden ejecutar independientemente entre sí. Muestran y guardan sus supuestos centrales. Cambiarlos en uno no cambia los otros: para comparar resultados, utiliza los mismos supuestos.

El diagnóstico `00_diagnostico_fuentes.ipynb` funciona por separado. Revisa Shiller, doce industrias de French, Baa/Aaa de FRED y diarios de Yahoo `^GSPC`. Compara medias y cierres sobre una muestra común; los resultados brutos allí no incluyen RF, dividendos o costes. Reutiliza originales y guarda sus tablas en `outputs/diagnosis/` al ejecutar la última celda. No sustituye las tablas de 01–06.

## Guardado y reproducción

Los cuadernos 01 y 02 escriben tablas en `data/processed/`. Regenerar una entrada retira los resultados que dependían de ella; vuelve a ejecutar las simulaciones que necesites. El 07 guarda `monthly_features.parquet` y su JSON; repetir la preparación de Shiller retira también esta tabla. Si actualizas los originales de contexto, debes repetir el 07. Cada cuaderno 03–06 guarda su propia tabla y resumen, conservando las demás simulaciones. Los JSON son salidas descriptivas, no archivos de configuración.

No se rellenan datos ausentes para forzar cobertura. El tramo desde 1990 queda excluido de estos cálculos. Las medias de Shiller no son precios de ejecución y su dividendo es una aproximación retrospectiva; estas limitaciones siguen vigentes en las simulaciones.

Para reproducir, reinicia el kernel y ejecuta todas las celdas. Antes del commit, usa **Clear All Outputs** y guarda el notebook. No incluyas datasets ni resultados voluminosos en Git.

Antes del 08, ejecuta **01 → 02 → 07**, en ese orden. Regenerar cualquiera de sus entradas retira las etiquetas anteriores. La estrategia final puede mantener posiciones; no deben capitalizarse los retornos aislados del etiquetado como si fueran esa estrategia. Antes del commit, limpia las salidas y guarda.
