# Cuadernos

Los notebooks sirven para comprender y explicar el análisis con texto, código y tablas. La lógica reutilizable pertenece a `src/tfm`: la CLI y los cuadernos llaman a las mismas funciones y leen `configs/estudio.toml`.

## Primer recorrido

Abre `01_datos_y_senales.ipynb` en un editor compatible con Jupyter (por ejemplo, VS Code con la extensión Jupyter) y selecciona `.venv/bin/python` como kernel en macOS/Linux, o `.venv/Scripts/python.exe` en Windows. La primera celda de código muestra el intérprete elegido.

Si falta el kernel, desde la raíz del proyecto y con `.venv` activado:

```bash
python -m pip install -e ".[notebooks]"
```

El extra añade `ipykernel` y `matplotlib` para el tercer cuaderno; no instala JupyterLab ni requiere registrar un kernel global cuando el editor detecta el entorno. El archivo `requirements-lock.txt` mantiene las versiones del flujo base y pytest; este extra se instala por separado.

Ejecuta las celdas en orden. El cuaderno:

1. Explica qué contienen P y D y qué periodos estudiaremos.
2. Prepara Shiller y calcula las señales usando las funciones existentes.
3. Muestra cobertura, primeras y últimas filas y el significado de cada señal.
4. Desglosa el cálculo de momentum y reversión para un mes concreto.

La preparación **escribe** en las rutas habituales de `data/raw/` y `data/processed/`. Si existe `data/raw/shiller.xls`, lo reutiliza; si falta, descarga el enlace configurado. También permite indicar un XLS local en la celda de preparación. No hace falta pasar antes por la CLI ni crear copias CSV. Volver a preparar regenera la tabla mensual y retira las señales anteriores; la siguiente llamada vuelve a calcularlas.

No se calculan rentabilidades de estrategias, dividendos mensuales aplicados, costes, etiquetas o modelos. Las variaciones que se muestran son los indicadores de precio utilizados para generar señales, no resultados de inversión. El periodo desde 1990 permanece fuera del análisis del cuaderno.

Para comprobar la reproducción, reinicia el kernel y ejecuta todas las celdas. Antes de guardar cambios para Git, limpia las salidas y los contadores de ejecución; no incrustes datos, credenciales ni resultados voluminosos. La primera ejecución puede necesitar acceso a Internet si no hay original de trabajo.

## Componentes de rentabilidad

`02_componentes_de_rentabilidad.ipynb` requiere haber preparado Shiller con el primer notebook o la opción 1. Selecciona `.venv` y reinicia el kernel si ya tenías importado el código antes de actualizarlo.

El segundo cuaderno prepara RF de French (descarga el ZIP si falta, o permite importar uno local), prepara la tabla de componentes y muestra las fórmulas para un mes elegido. Conserva las tasas en decimal y convierte a porcentaje únicamente para presentarlas. RF es la alternativa de efectivo: no se suma a los componentes del índice.

También puedes usar la CLI: opciones 6 → 7 → 3. No se aplican aún señales ni costes y no se calculan resultados de estrategias. Repetir el primer notebook regenera Shiller y retira los componentes anteriores, que debes volver a preparar con el segundo.

## Simulación de estrategias básicas

`03_estrategias_basicas.ipynb` requiere Shiller, señales y componentes preparados (notebooks 01 y 02, u opciones 1 → 2 → 6 → 7). Reinicia el kernel después de actualizar el código y selecciona `.venv`. Para disponer de las curvas, instala el extra actualizado con `python -m pip install -e ".[notebooks]"` si aún no tienes matplotlib.

El cuaderno muestra los supuestos antes de ejecutar, llama al mismo simulador que la opción 8 y permite ver el balance de un mes, las curvas de capital/caídas y las métricas de las tres estrategias. La escala logarítmica del gráfico es una opción de presentación, no un cambio de resultados. No se usan datos desde 1990 ni se seleccionan filtros o modelos.

Las simulaciones se guardan con nombres fijos y quedan obsoletas al regenerar cualquiera de sus entradas o modificar los parámetros. El cuaderno no prepara ni descarga fuentes automáticamente. Antes de hacer commit, usa «Clear All Outputs» y guarda el notebook.

## Comparación de costes y dividendos

`04_sensibilidad.ipynb` necesita las mismas entradas preparadas que el notebook 03, aunque no exige ejecutarlo antes. Selecciona `.venv`, reinicia el kernel y ejecuta las celdas en orden. No necesita nuevas dependencias.

Primero muestra todos los escenarios y sus parámetros. Después ejecuta la comparación con el mismo simulador de la opción 9 y presenta una tabla por estrategia y un gráfico de rentabilidades anualizadas. Solo cambia un supuesto cada vez respecto a `[simulation]`: negociación, préstamo anual o inclusión del dividendo aproximado. Con la configuración inicial son siete escenarios y 21 resúmenes.

La celda de ejecución escribe o sustituye `data/processed/baseline_sensitivity.parquet` y su JSON. No descarga, no edita `estudio.toml` y no sobrescribe la cuenta mensual del notebook 03. No selecciona el mejor escenario ni utiliza fechas desde 1990. El cambio de rentabilidad se expresa en puntos porcentuales respecto al central. Se conservan el orden declarado y las limitaciones de Shiller. Limpia las salidas y guarda antes de hacer commit.

## Filtro de mercado bajista

`05_filtro_bajista.ipynb` compara las dos reglas originales y las dos filtradas, junto con comprar y mantener. Primero repite los notebooks 01 y 02: el filtro necesita precios desde diciembre de 1924 y la configuración se ha ampliado para mantener todos los meses de 1927–1989. La historia adicional es calentamiento, no más meses de evaluación. Se reutilizan los originales; no se necesita otra fuente.

Después selecciona `.venv`, reinicia el kernel y ejecuta el 05 en orden. Muestra la regla de 24 meses, ejecuta la misma comparación que la opción 10, explica mayo de 1975 y representa capital y caídas por regla. La ejecución escribe `bear_filter_simulations.parquet` y su JSON, sin descargar ni sobrescribir las otras simulaciones. Es una adaptación declarada del indicador de Daniel y Moskowitz a nuestros datos, no una réplica del artículo. No incluye aún ajuste por volatilidad ni aprendizaje automático. Guarda el notebook sin salidas antes del commit.
