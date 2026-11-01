"""Diagnóstico previo: originales separados, cobertura y efecto de promediar.

No lee configuraciones, no usa importes desde 1990 y no entrena modelos.
Las salidas de las simulaciones existentes no se preparan ni se sustituyen.
"""

import csv
from io import BytesIO, StringIO
from itertools import combinations
import math
from pathlib import Path
import ssl
from urllib.request import Request, urlopen
from zipfile import ZipFile

import certifi
import pandas as pd

from tfm.preparation.shiller import normalize_shiller
from tfm.signals.shiller import price_rule_values
from tfm.sources.shiller import SOURCE_URL as SHILLER_URL
from tfm.sources.prices import fetch_prices


START = "1927-01"
END = "1989-12"
HISTORY_START = "1924-12"
MONTHS = pd.period_range(START, END, freq="M").astype(str)
INDUSTRIES = ["NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq", "Telcm", "Utils", "Shops", "Hlth", "Money", "Other"]
SOURCE_URLS = {
    "shiller": SHILLER_URL,
    "industries": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/12_Industry_Portfolios_CSV.zip",
    "BAA": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAA&cosd=1919-01-01&coed=1989-12-31",
    "AAA": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=AAA&cosd=1919-01-01&coed=1989-12-31",
    "yahoo": "https://finance.yahoo.com/quote/%5EGSPC/history/",
}
PRICE_NAMES = {"shiller_mean": "Media de Shiller", "yahoo_mean": "Media diaria de Yahoo", "yahoo_close": "Último cierre de Yahoo"}


def _check_months(periods, *, start: str | None = None, end: str | None = None) -> None:
    periods = list(periods)
    if not periods:
        raise ValueError("La fuente no contiene meses dentro del intervalo solicitado")
    expected = pd.period_range(start or periods[0], end or periods[-1], freq="M").astype(str).tolist()
    if periods != expected:
        raise ValueError("La fuente contiene meses ausentes, duplicados o desordenados; no se han rellenado")


def _check_numbers(table: pd.DataFrame, *, positive: bool = False) -> None:
    for column in table:
        values = table[column]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or values.isna().any() or not values.map(math.isfinite).all()
                or (positive and values.le(0).any())):
            raise ValueError(f"Importes inválidos o ausentes en {column}")


def parse_industry_returns(content: bytes) -> pd.DataFrame:
    """Solo el primer bloque mensual, ponderado por valor; porcentaje a decimal."""
    with ZipFile(BytesIO(content)) as archive:
        member = "12_Industry_Portfolios.csv"
        if member not in archive.namelist() or archive.getinfo(member).file_size > 10 * 1024 * 1024:
            raise ValueError("ZIP de las doce industrias incompatible")
        lines = archive.read(member).decode("utf-8-sig").splitlines()
    marker = next((i for i, line in enumerate(lines) if line.strip() == "Average Value Weighted Returns -- Monthly"), None)
    if marker is None or next(csv.reader([lines[marker + 1]]))[1:] != INDUSTRIES:
        raise ValueError("No se encuentra la tabla mensual ponderada por valor de las doce industrias")
    records = []
    for fields in csv.reader(lines[marker + 2:]):
        if not fields or not fields[0].strip():
            break
        token = fields[0].strip()
        if len(token) != 6 or not token.isdigit():
            raise ValueError("Fecha incompatible en la tabla mensual de industrias")
        period = str(pd.Period(f"{token[:4]}-{token[4:]}", freq="M"))
        if not "1926-07" <= period <= END:
            continue  # No convertir importes de la prueba final.
        if len(fields) != 13:
            raise ValueError("Faltan columnas en la tabla de industrias")
        values = [float(value) for value in fields[1:]]
        if any(value in (-99.99, -999) or not math.isfinite(value) or value <= -100 for value in values):
            raise ValueError("Retornos industriales ausentes o incompatibles; no se han rellenado")
        records.append({"period": period, **{name: value / 100 for name, value in zip(INDUSTRIES, values)}})
    table = pd.DataFrame(records, columns=["period", *INDUSTRIES])
    _check_months(table.period, start="1926-07", end=END)
    return table


def parse_fred_yield(content: bytes, series: str) -> pd.DataFrame:
    """Tipos anuales en porcentaje: NO son retornos mensuales y NO son RF."""
    if series not in ("BAA", "AAA"):
        raise ValueError("Este diagnóstico utiliza únicamente BAA y AAA")
    reader = csv.DictReader(StringIO(content.decode("utf-8-sig")))
    if reader.fieldnames != ["observation_date", series]:
        raise ValueError(f"CSV de FRED incompatible con {series}")
    records = []
    for row in reader:
        date = pd.Timestamp(row["observation_date"])
        if date.day != 1:
            raise ValueError("Se esperaba una serie mensual de FRED")
        period = str(date.to_period("M"))
        if "1919-01" <= period <= END:
            records.append({"period": period, "yield_percent": float(row[series])})
    table = pd.DataFrame(records, columns=["period", "yield_percent"])
    _check_months(table.period, start="1919-01", end=END)
    _check_numbers(table[["yield_percent"]])
    return table


def yahoo_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Última observación disponible y promedio; no certifica todas las sesiones."""
    if (daily.empty or "Close" not in daily or not isinstance(daily.index, pd.DatetimeIndex)
            or daily.index.tz is not None or daily.index.hasnans
            or daily.index.has_duplicates or not daily.index.is_monotonic_increasing):
        raise ValueError("Yahoo requiere fechas de sesión únicas, ordenadas y sin zona horaria")
    if (daily.index < pd.Timestamp("1920-01-01")).any() or (daily.index >= pd.Timestamp("1990-01-01")).any():
        raise ValueError("Hay sesiones fuera del intervalo solicitado; no se utilizarán datos desde 1990")
    _check_numbers(daily[["Close"]], positive=True)
    frame = pd.DataFrame({"period": daily.index.to_period("M").astype(str),
                          "session": daily.index, "close": daily.Close.to_numpy()})
    table = frame.groupby("period", sort=True).agg(yahoo_close=("close", "last"),
                                                   yahoo_mean=("close", "mean"),
                                                   sessions=("close", "size"),
                                                   last_session=("session", "max")).reset_index()
    _check_months(table.period, end=END)
    # El primer mes puede empezar a mitad: no confundir su media parcial con una media mensual.
    table["mean_usable"] = True
    table.loc[0, "mean_usable"] = False
    return table


def _load_original(path: Path, url: str, reader):
    exists = path.exists()
    if exists:
        content = path.read_bytes()
    else:
        context = ssl.create_default_context(cafile=certifi.where())
        request = Request(url, headers={"User-Agent": "UOCDataScienceTFM/0.1 (academic research)"})
        with urlopen(request, context=context, timeout=30) as response:
            content = response.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("Original demasiado grande para este diagnóstico")
    table = reader(content)  # Validar antes de conservar una descarga nueva.
    if not exists:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return table


def load_context_sources(root: str | Path) -> dict[str, pd.DataFrame]:
    """Industrias y crédito para variables, sin descargar Shiller ni Yahoo."""
    folder = Path(root) / "data/raw/diagnosis"
    sources = {"industries": _load_original(folder / "12_industries.zip", SOURCE_URLS["industries"], parse_industry_returns)}
    for series in ("BAA", "AAA"):
        sources[series] = _load_original(folder / f"{series.lower()}.csv", SOURCE_URLS[series],
                                         lambda content, name=series: parse_fred_yield(content, name))
    return sources


def load_diagnostic_sources(root: str | Path) -> dict[str, pd.DataFrame]:
    """Reutilizar originales; nuevos archivos separados, sin tocar las tablas de trabajo."""
    raw = Path(root) / "data/raw"
    folder = raw / "diagnosis"
    def read_shiller(content):
        table, report = normalize_shiller(content, history_start=HISTORY_START)
        if report["status"] != "passed":
            raise ValueError(f"Shiller no supera los controles: {report['error_counts']}")
        return table
    sources = {"shiller": _load_original(raw / "shiller.xls", SOURCE_URLS["shiller"], read_shiller),
               **load_context_sources(root)}
    path = folder / "gspc_daily_1920_1989.parquet"
    if path.exists():
        daily = pd.read_parquet(path)
    else:
        daily = fetch_prices({"tickers": "^GSPC", "start": "1920-01-01", "end": "1990-01-01",
                              "interval": "1d", "auto_adjust": False, "back_adjust": False,
                              "actions": True, "repair": False, "threads": False,
                              "multi_level_index": False, "ignore_tz": True, "progress": False,
                              "timeout": 30, "keepna": True, "rounding": False, "prepost": False,
                              "group_by": "column"})
    sources["yahoo"] = yahoo_monthly(daily)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        daily.to_parquet(path)
    return sources


def coverage_table(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    records = []
    for name, table in sources.items():
        available = set(table.period)
        missing = [month for month in MONTHS if month not in available]
        records.append({"source": name, "first_analyzed_month": table.period.iloc[0],
                        "last_analyzed_month": table.period.iloc[-1], "rows": len(table),
                        "development_months": len(MONTHS) - len(missing),
                        "missing_development_months": len(missing),
                        "first_missing_months": ", ".join(missing[:12]), "source_url": SOURCE_URLS[name]})
    return pd.DataFrame(records)


def compare_price_definitions(shiller: pd.DataFrame, yahoo: pd.DataFrame) -> dict[str, pd.DataFrame]:
    series = {"shiller_mean": shiller.set_index("period").price_monthly_mean,
              "yahoo_mean": yahoo.loc[yahoo.mean_usable].set_index("period").yahoo_mean,
              "yahoo_close": yahoo.set_index("period").yahoo_close}
    for values in series.values():
        _check_months(values.index)
        _check_numbers(values.to_frame(), positive=True)
    start = max(START, *(values.index[0] for values in series.values()))
    end = min(END, *(values.index[-1] for values in series.values()))
    months = pd.period_range(start, end, freq="M").astype(str)
    if len(months) < 14:
        raise ValueError("No hay historia común suficiente para comparar ambas reglas y su resultado posterior")
    prices = pd.DataFrame({name: values.loc[months].to_numpy() for name, values in series.items()}, index=months)
    prices.index.name = "period"
    changes = prices / prices.shift(1) - 1
    signals = {name: price_rule_values(prices[name]) for name in prices}
    # Misma historia inicial y mismas decisiones maduras para todas las series y reglas.
    decisions = prices.index[12:-1]
    targets = (pd.PeriodIndex(decisions, freq="M") + 1).astype(str)
    records, statistics = [], []
    for name, scores in signals.items():
        selected = scores.loc[decisions]
        outcome = changes.loc[targets, name].to_numpy()
        for i, month in enumerate(decisions):
            records.append({"basis": name, "decision_period": month, "target_period": targets[i],
                            "momentum_score": float(selected.momentum_score.iloc[i]),
                            "reversal_score": float(selected.reversal_score.iloc[i]),
                            "momentum_signal": int(selected.momentum_signal.iloc[i]),
                            "reversal_signal": int(selected.reversal_signal.iloc[i]),
                            "target_price_return": float(outcome[i])})
        stats = changes.loc[targets, name]
        statistics.append({"basis": name, "first_target": targets[0], "last_target": targets[-1],
                           "months": len(targets), "annualized_price_volatility": float(stats.std(ddof=1) * math.sqrt(12)),
                           "lag1_price_return_correlation": float(stats.autocorr(1)),
                           "momentum_mean_gross_price_payoff": float((selected.momentum_signal.to_numpy(dtype=float) * outcome).mean()),
                           "reversal_mean_gross_price_payoff": float((selected.reversal_signal.to_numpy(dtype=float) * outcome).mean())})
    table = pd.DataFrame(records)
    agreement = []
    for left, right in combinations(signals, 2):
        for rule in ("momentum", "reversal"):
            column = f"{rule}_signal"
            different = int(signals[left].loc[decisions, column].ne(signals[right].loc[decisions, column]).sum())
            agreement.append({"left": left, "right": right, "rule": rule, "months": len(decisions),
                              "different_signals": different, "different_fraction": different / len(decisions)})
    differences = prices.copy()
    differences["shiller_minus_yahoo_mean_fraction"] = differences.shiller_mean / differences.yahoo_mean - 1
    differences["shiller_minus_yahoo_close_fraction"] = differences.shiller_mean / differences.yahoo_close - 1
    largest = differences.loc[differences.shiller_minus_yahoo_mean_fraction.abs().nlargest(5).index]
    return {"prices": prices.reset_index(), "returns": changes.iloc[1:].reset_index(),
            "signals": table, "statistics": pd.DataFrame(statistics), "agreement": pd.DataFrame(agreement),
            "source_discrepancies": largest.reset_index()}


def feature_availability(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Cobertura inicial propuesta; los rezagos NO acreditan versiones históricas."""
    price_months = pd.PeriodIndex(sources["shiller"].period, freq="M")
    industry_months = pd.PeriodIndex(sources["industries"].period, freq="M")
    credit_months = pd.PeriodIndex(sources["BAA"].period, freq="M")
    if sources["BAA"].period.tolist() != sources["AAA"].period.tolist():
        raise ValueError("BAA y AAA no cubren los mismos meses")
    candidates = [
        ("Retorno de un mes", price_months[1:] + 1, 0),
        ("Momentum 12–1", price_months[12:] + 1, 0),
        ("Retorno acumulado de 24 meses", price_months[24:] + 1, 0),
        ("Distancia a media de 12 meses", price_months[11:] + 1, 0),
        ("Volatilidad de 12 variaciones", price_months[12:] + 1, 0),
        ("Caída desde máximo de 12 meses", price_months[11:] + 1, 0),
        ("Dispersión entre industrias", industry_months + 2, 1),
        ("Amplitud industrial sobre media de 12 meses", industry_months[11:] + 2, 1),
        ("Diferencial Baa–Aaa", credit_months + 2, 1),
        ("Variación del diferencial", credit_months[1:] + 2, 1),
    ]
    records = []
    for name, targets, lag in candidates:
        available = [str(month) for month in targets if START <= str(month) <= END]
        records.append({"feature": name, "first_available_target": available[0] if available else None,
                        "last_available_target": available[-1] if available else None,
                        "development_months": len(available), "extra_publication_lag_months": lag})
    return pd.DataFrame(records)
