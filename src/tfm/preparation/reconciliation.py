"""Contraste de distribuciones monetarias por fecha exdividendo, sin reparar datos."""

import math
import pandas as pd


RECONCILIATION_VERSION = 1
ABSOLUTE_TOLERANCE_USD = 0.0005005
DETAIL_COLUMNS = ["observed_at", "yahoo_distribution", "ssga_distribution", "income_dividend",
                  "short_term_gain", "long_term_gain", "absolute_difference", "result"]


def reconcile_dividends(prices: pd.DataFrame, reference: pd.DataFrame, coverage: dict,
                        start: str, end_exclusive: str, *, tolerance: float) -> tuple[dict, pd.DataFrame]:
    """Todos los eventos de la intersección; nunca solo los que coinciden en fecha."""
    if tolerance != ABSOLUTE_TOLERANCE_USD:
        raise ValueError("Tolerancia distinta del protocolo versionado de distribuciones")
    left = max(pd.Timestamp(start), pd.Timestamp(coverage["start"]))
    right = min(pd.Timestamp(end_exclusive), pd.Timestamp(coverage["end_exclusive"]))
    complete = left == pd.Timestamp(start) and right == pd.Timestamp(end_exclusive)
    base = {"coverage": "complete" if complete else "partial" if left < right else "none",
            "agreement": "not_evaluated", "absolute_tolerance_usd": tolerance, "relative_tolerance": 0,
            "date_basis": "ex_date", "amount_basis": "total_cash_distribution_usd_per_share",
            "requested_interval": {"start": start, "end_exclusive": end_exclusive},
            "evaluated_interval": None if left >= right else {"start": str(left.date()), "end_exclusive": str(right.date())}}
    if left >= right:
        return {**base, "status": "not_evaluated", "events": 0, "discrepancies": 0}, pd.DataFrame(columns=DETAIL_COLUMNS)
    sample = prices.loc[prices["observed_at"].ge(left) & prices["observed_at"].lt(right)]
    if not sample["dividends"].map(math.isfinite).all() or sample["dividends"].lt(0).any():
        raise ValueError("Dividendos Yahoo inválidos")
    if sample["stock_splits"].ne(0).any():
        raise ValueError("Hay splits en el intervalo; este adaptador no equipara importes ajustados por splits")
    yahoo = sample.loc[sample["dividends"].ne(0), ["observed_at", "dividends"]].rename(columns={"dividends": "yahoo_distribution"})
    ssga = reference.loc[reference["observed_at"].ge(left) & reference["observed_at"].lt(right)].rename(columns={"cash_distribution": "ssga_distribution"})
    details = yahoo.merge(ssga, how="outer", on="observed_at", validate="one_to_one", indicator=True).sort_values("observed_at")
    details["absolute_difference"] = (details["yahoo_distribution"] - details["ssga_distribution"]).abs()
    details["result"] = "within_tolerance"
    details.loc[details["absolute_difference"].gt(tolerance), "result"] = "amount_mismatch"
    details.loc[details["_merge"].eq("left_only"), "result"] = "missing_in_reference"
    details.loc[details["_merge"].eq("right_only"), "result"] = "missing_in_yahoo"
    details = details.reindex(columns=DETAIL_COLUMNS).reset_index(drop=True)
    discrepancies = int(details["result"].ne("within_tolerance").sum())
    agreement = "discrepant" if discrepancies else "within_tolerance" if len(details) else "not_evaluated"
    status = "failed" if discrepancies else "not_evaluated" if not len(details) else "passed" if complete else "partial"
    return {**base, "status": status, "agreement": agreement, "events": len(details),
            "matched_events": int(details["result"].eq("within_tolerance").sum()), "discrepancies": discrepancies,
            "missing_in_yahoo": int(details["result"].eq("missing_in_yahoo").sum()),
            "missing_in_reference": int(details["result"].eq("missing_in_reference").sum()),
            "max_absolute_difference": None if details["absolute_difference"].dropna().empty else float(details["absolute_difference"].max())}, details
