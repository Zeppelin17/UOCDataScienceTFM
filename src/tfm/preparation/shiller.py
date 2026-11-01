"""Observaciones mensuales de Shiller: selección temporal y controles de datos."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
import tomllib

import pandas as pd
import xlrd

from tfm.sources.shiller import INSTRUMENT


COLUMNS = ["asset", "period", "price_monthly_mean", "dividend_annualized", "sample_role", "source"]
LIMITATIONS = [
    "P es un promedio mensual nominal; no un cierre, precio de orden o cierre ajustado de SPY.",
    "D es anualizado e interpolado; no es un pago mensual ni un predictor conocido en tiempo real.",
    "Los controles son de estructura y cobertura; no certifican exactitud, disponibilidad histórica o ejecución.",
    "Esta tabla contiene observaciones; las señales, componentes y simulaciones se calculan en pasos separados.",
]

def _month(value) -> str:
    """YYYY.MM numérico: 1926.1 es octubre, no enero."""
    if isinstance(value, bool):
        raise ValueError("Mes Shiller inválido")
    try:
        number = Decimal(str(value).strip())
        scaled = number * 100
        integer = scaled.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if not number.is_finite() or abs(scaled - integer) > Decimal("0.000001"):
            raise ValueError("Fecha Shiller inválida; se esperaba YYYY.MM")
        year, month = divmod(int(integer), 100)
        if not 1800 <= year <= 2099 or not 1 <= month <= 12:
            raise ValueError("Mes Shiller fuera de rango")
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("Fecha Shiller inválida; se esperaba YYYY.MM") from exc
    return f"{year:04d}-{month:02d}"



def preparation_window(history_start: str, policy_bytes: bytes | None = None) -> tuple[str, str, str]:
    expected = {"development_start": "1927-01-01", "development_end": "1989-12-31",
                "final_test_start": "1990-01-01", "final_test_end": "pending"}
    policy = tomllib.loads(policy_bytes.decode("utf-8"))["validation"] if policy_bytes is not None else expected
    if policy != expected:
        raise ValueError("Este flujo exige desarrollo 1927–1989 y evaluación desde 1990 aún deshabilitada")
    try:
        start = pd.Period(history_start, freq="M")
    except (ValueError, TypeError) as exc:
        raise ValueError("history_start debe tener formato YYYY-MM") from exc
    if str(start) != history_start or not pd.Period("1871-01", freq="M") <= start <= pd.Period("1926-01", freq="M"):
        raise ValueError("La historia previa debe comenzar entre 1871-01 y 1926-01")
    return history_start, policy["development_start"][:7], policy["development_end"][:7]



def normalize_shiller(content: bytes, *, history_start: str, policy_bytes: bytes | None = None) -> tuple[pd.DataFrame, dict]:
    start, development_start, end = preparation_window(history_start, policy_bytes)
    try:
        book = xlrd.open_workbook(file_contents=content, on_demand=True)
    except xlrd.XLRDError as exc:
        raise ValueError("No se pudo leer el Excel XLS original de Shiller") from exc
    try:
        try:
            sheet = book.sheet_by_name("Data")
        except xlrd.XLRDError as exc:
            raise ValueError("Falta la hoja Data del Excel de Shiller") from exc
        if sheet.nrows < 9 or sheet.ncols < 3 or sheet.row_values(7, 0, 3) != ["Date", "P", "D"]:
            raise ValueError("Cabecera Shiller incompatible; revisar el adaptador antes de continuar")
        selected, original_periods = [], []
        for i in range(8, sheet.nrows):
            value = sheet.cell_value(i, 0)
            if value == "":
                continue
            period = _month(value)
            original_periods.append(period)
            if not start <= period <= end:
                continue  # No leer importes del bloque de evaluación ni otros campos.
            amounts = []
            for column in (1, 2):
                cell = sheet.cell(i, column)
                amounts.append(float(cell.value) if cell.ctype == xlrd.XL_CELL_NUMBER else float("nan"))
            selected.append({"asset": INSTRUMENT, "period": period,
                             "price_monthly_mean": amounts[0], "dividend_annualized": amounts[1],
                             "sample_role": "history" if period < development_start else "development",
                             "source": "shiller"})
    finally:
        book.release_resources()
    table = pd.DataFrame(selected, columns=COLUMNS).sort_values("period", kind="stable").reset_index(drop=True)
    expected = pd.period_range(start, end, freq="M").astype(str).tolist()
    counts = {
        "empty": int(table.empty), "duplicate_months": int(table.period.duplicated().sum()),
        "missing_months": len(set(expected) - set(table.period)),
        "non_finite_values": int(sum(not math.isfinite(value) for name in ("price_monthly_mean", "dividend_annualized") for value in table[name])),
        "non_positive_prices": int(table.price_monthly_mean.le(0).sum()),
        "negative_dividends": int(table.dividend_annualized.lt(0).sum()),
    }
    report = {
        "status": "failed" if any(counts.values()) else "passed", "scope": "structure_and_monthly_coverage_only",
        "rows": len(table), "history_rows": int(table.sample_role.eq("history").sum()),
        "development_rows": int(table.sample_role.eq("development").sum()),
        "first_period": None if table.empty else table.period.iloc[0],
        "last_period": None if table.empty else table.period.iloc[-1], "error_counts": counts,
        "missing_months": sorted(set(expected) - set(table.period)),
        "interval": {"history_start": start, "development_start": development_start, "development_end": end},
        "original_date_coverage": {"first_period": min(original_periods) if original_periods else None,
                                   "last_period": max(original_periods) if original_periods else None},
        "excluded_original_rows": len(original_periods) - len(table),
        "selected_source_columns": ["Date", "P", "D"], "warnings": LIMITATIONS,
    }
    return table, report
