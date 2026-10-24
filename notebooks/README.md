# Cuadernos

Los notebooks sirven para comprender y explicar el análisis con texto, código y tablas. La lógica reutilizable pertenece a `src/tfm`: la CLI y los cuadernos llaman a las mismas funciones y leen `configs/estudio.toml`.

## Primer recorrido

Abre `01_datos_y_senales.ipynb` en un editor compatible con Jupyter (por ejemplo, VS Code con la extensión Jupyter) y selecciona `.venv/bin/python` como kernel en macOS/Linux, o `.venv/Scripts/python.exe` en Windows. La primera celda de código muestra el intérprete elegido.

Si falta el kernel, desde la raíz del proyecto y con `.venv` activado:

```bash
python -m pip install -e ".[notebooks]"
```

El extra añade `ipykernel`; no instala JupyterLab ni requiere registrar un kernel global cuando el editor detecta el entorno. El archivo `requirements-lock.txt` mantiene las versiones del flujo base y pytest; este extra se instala por separado.

Ejecuta las celdas en orden. El cuaderno:

1. Explica qué contienen P y D y qué periodos estudiaremos.
2. Prepara Shiller y calcula las señales usando las funciones existentes.
3. Muestra cobertura, primeras y últimas filas y el significado de cada señal.
4. Desglosa el cálculo de momentum y reversión para un mes concreto.

La preparación **escribe** en las rutas habituales de `data/raw/` y `data/processed/`. Si existe `data/raw/shiller.xls`, lo reutiliza; si falta, descarga el enlace configurado. También permite indicar un XLS local en la celda de preparación. No hace falta pasar antes por la CLI ni crear copias CSV. Volver a preparar regenera la tabla mensual y retira las señales anteriores; la siguiente llamada vuelve a calcularlas.

No se calculan rentabilidades de estrategias, dividendos mensuales aplicados, costes, etiquetas o modelos. Las variaciones que se muestran son los indicadores de precio utilizados para generar señales, no resultados de inversión. El periodo desde 1990 permanece fuera del análisis del cuaderno.

Para comprobar la reproducción, reinicia el kernel y ejecuta todas las celdas. Antes de guardar cambios para Git, limpia las salidas y los contadores de ejecución; no incrustes datos, credenciales ni resultados voluminosos. La primera ejecución puede necesitar acceso a Internet si no hay original de trabajo.
