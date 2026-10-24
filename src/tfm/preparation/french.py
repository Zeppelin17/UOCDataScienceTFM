"""Extraer solo RF mensual: sin usar factores bursátiles ni retornos anuales."""

import csv
from io import BytesIO, StringIO
import math
import re
from zipfile import BadZipFile, ZipFile

import pandas as pd


COLUMNS = ["period", "rf_return"]


def validate_rf(table: pd.DataFrame, *, start: str, end: str) -> None:
    expected = pd.period_range(start, end, freq="M").astype(str).tolist()
    if table.columns.tolist() != COLUMNS or table.empty or table.period.tolist() != expected:
        raise ValueError("RF debe cubrir todos los meses del desarrollo, ordenados y sin duplicados ni huecos")
    values = table.rf_return
    if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
            or not values.map(math.isfinite).all() or values.le(-1).any()
            or values.isin([-0.9999, -9.99]).any()):
        raise ValueError("RF contiene valores ausentes o inválidos; no se rellenan ni sustituyen por cero")


def normalize_french_rf(content: bytes, *, start: str, end: str) -> tuple[pd.DataFrame, dict]:
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = [info for info in archive.infolist()
                       if info.filename == "F-F_Research_Data_Factors.csv"]
            if len(members) != 1 or members[0].file_size > 10 * 1024 * 1024:
                raise ValueError("El ZIP debe contener el CSV mensual de tres factores de French")
            text = archive.read(members[0]).decode("utf-8-sig")
    except (BadZipFile, UnicodeError, RuntimeError) as exc:
        raise ValueError("No se pudo leer el ZIP CSV original de French") from exc
    reader = csv.reader(StringIO(text))
    for row in reader:
        if [field.strip() for field in row] == ["", "Mkt-RF", "SMB", "HML", "RF"]:
            break
    else:
        raise ValueError("Cabecera de French incompatible: se esperaba RF en el CSV mensual")
    selected = []
    started = False
    for row in reader:
        month = row[0].strip() if row else ""
        if not re.fullmatch(r"\d{6}", month):
            if started:
                break  # Fin del bloque mensual: no mezclar la tabla anual.
            continue
        started = True
        period = f"{month[:4]}-{month[4:]}"
        if not start <= period <= end:
            continue  # No convertir importes anteriores ni posteriores al desarrollo.
        if len(row) != 5:
            raise ValueError(f"Fila mensual de French incompatible: {period}")
        try:
            value = float(row[4])
        except ValueError as exc:
            raise ValueError(f"RF no es numérico en {period}") from exc
        if value in {-99.99, -999}:
            raise ValueError(f"RF contiene un código de dato ausente en {period}")
        selected.append({"period": period, "rf_return": value / 100})
    table = pd.DataFrame(selected, columns=COLUMNS)
    validate_rf(table, start=start, end=end)
    return table, {"status": "passed", "rows": len(table), "first_period": start, "last_period": end,
                   "selected_source_columns": ["date", "RF"], "source_unit": "monthly_percent",
                   "output_unit": "decimal_monthly_return",
                   "warnings": ["RF es la rentabilidad mensual del Treasury bill a un mes, no del S&P.",
                                "El ZIP reconstruye la historia; no acredita versiones publicadas en cada fecha.",
                                "Se excluyen los importes desde 1990 y los demás factores."]}
