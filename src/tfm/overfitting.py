"""DSR y PBO sobre los retornos cronológicos del periodo de desarrollo."""

from datetime import datetime, timezone
from itertools import combinations
from math import ceil, e, sqrt
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from tfm.economic_validation import TEST_INTERVAL
from tfm.screening import RULES
from tfm.selection_returns import FILTERS, RESULT_NAME as SELECTION_RETURNS


RESULT_NAMES = ("development_dsr", "development_pbo", "development_pbo_splits")
PBO_BLOCKS = 16
MIN_DEVIATION = 1e-12
MONTHS_PER_YEAR = 12
ANNUAL_SCALE = sqrt(MONTHS_PER_YEAR)
NORMAL = NormalDist()


def _checked_returns(excess: pd.DataFrame) -> np.ndarray:
    if excess.shape[0] < 4 or excess.shape[1] < 2 or not excess.columns.is_unique:
        raise ValueError("Se necesitan al menos cuatro retornos y dos candidatos distintos.")
    values = excess.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values.std(axis=0, ddof=1) <= MIN_DEVIATION).any():
        raise ValueError("Cada candidato requiere retornos finitos y varianza positiva.")
    return values


def _expected_max_sharpe(sharpe_std: float, trials: int) -> float:
    if trials == 1:
        return 0.0
    return sharpe_std * (
        (1 - np.euler_gamma) * NORMAL.inv_cdf(1 - 1 / trials)
        + np.euler_gamma * NORMAL.inv_cdf(1 - 1 / (trials * e))
    )


def deflated_sharpe(excess: pd.DataFrame) -> pd.DataFrame:
    """Calcular el DSR mensual con el número efectivo y con todos los ensayos."""
    values = _checked_returns(excess)
    months, trials = values.shape
    sharpe = values.mean(axis=0) / values.std(axis=0, ddof=1)
    centered = values - values.mean(axis=0)
    standardized = centered / np.sqrt((centered**2).mean(axis=0))
    skewness = (standardized**3).mean(axis=0)
    kurtosis = (standardized**4).mean(axis=0)
    sampling_variance = 1 - skewness * sharpe + (kurtosis - 1) * sharpe**2 / 4
    if (sampling_variance <= 0).any():
        raise ValueError("El error estándar del Sharpe no es estimable.")
    error = np.sqrt(sampling_variance / (months - 1))
    pairs = np.corrcoef(values, rowvar=False)[np.triu_indices(trials, k=1)]
    mean_correlation = float(pairs.mean())
    effective_trials = 1 + (trials - 1) * (1 - float(np.clip(mean_correlation, 0, 1)))
    trials_used = ceil(round(effective_trials, 12))
    sharpe_std = float(sharpe.std(ddof=1))
    benchmark = _expected_max_sharpe(sharpe_std, trials_used)
    independent_benchmark = _expected_max_sharpe(sharpe_std, trials)
    return pd.DataFrame({"policy": excess.columns.tolist(), "months": months, "trials": trials,
        "mean_return_correlation": mean_correlation, "effective_trials": effective_trials,
        "trials_used": trials_used, "sharpe_annualized": sharpe * ANNUAL_SCALE,
        "sharpe_dispersion_annualized": sharpe_std * ANNUAL_SCALE, "skewness": skewness, "kurtosis": kurtosis,
        "benchmark_annualized": benchmark * ANNUAL_SCALE,
        "independent_benchmark_annualized": independent_benchmark * ANNUAL_SCALE,
        "dsr": [NORMAL.cdf(float(z)) for z in (sharpe - benchmark) / error],
        "dsr_all_independent": [NORMAL.cdf(float(z)) for z in (sharpe - independent_benchmark) / error]})


def _block_sharpe(membership: np.ndarray, totals: np.ndarray, squares: np.ndarray, months: int) -> np.ndarray:
    sums = membership @ totals
    mean = sums / months
    variance = (membership @ squares - sums * mean) / (months - 1)
    if (variance <= MIN_DEVIATION ** 2).any():
        raise ValueError("Hay valores de Sharpe no estimables en CSCV. Revisa los candidatos y la cobertura.")
    return mean / np.sqrt(variance) * ANNUAL_SCALE


def combinatorial_pbo(excess: pd.DataFrame, *, blocks: int = PBO_BLOCKS) -> tuple[dict, pd.DataFrame]:
    """Elegir por Sharpe en media muestra y calcular el rango complementario."""
    ordered = excess.sort_index(axis=1)
    values = _checked_returns(ordered)
    months, trials = values.shape
    if blocks < 2 or blocks % 2 or months % blocks or blocks > months:
        raise ValueError("CSCV requiere un número par de bloques consecutivos de igual longitud.")
    months_per_block = months // blocks
    halves = np.array(list(combinations(range(blocks), blocks // 2)))
    membership = np.zeros((len(halves), blocks), dtype=bool)
    rows = np.arange(len(halves))
    membership[rows[:, None], halves] = True
    chunks = values.reshape(blocks, months_per_block, trials)
    totals = chunks.sum(axis=1)
    squares = (chunks**2).sum(axis=1)
    ins = _block_sharpe(membership, totals, squares, months // 2)
    oos = _block_sharpe(~membership, totals, squares, months // 2)
    best = ins.argmax(axis=1)
    in_score, out_score = ins[rows, best], oos[rows, best]
    in_ties = (ins == in_score[:, None]).sum(axis=1)
    out_ties = (oos == out_score[:, None]).sum(axis=1)
    rank = 1 + (oos < out_score[:, None]).sum(axis=1) + (out_ties - 1) / 2
    relative_rank = rank / (trials + 1)
    logit = np.log(relative_rank / (1 - relative_rank))
    splits = pd.DataFrame({
        "split_id": rows + 1, "selection_blocks": [",".join(map(str, b + 1)) for b in halves],
        "selected_policy": ordered.columns.to_numpy()[best], "selection_ties": in_ties,
        "sharpe_selection": in_score, "sharpe_complement": out_score,
        "complement_rank": rank, "relative_rank": relative_rank, "logit": logit,
        "below_median": relative_rank < .5, "at_median": relative_rank == .5,
    })
    below_median = int(splits.below_median.sum())
    negative = int((out_score < 0).sum())
    summary = {"months": months, "trials": trials, "blocks": blocks,
        "months_per_block": months_per_block, "months_per_half": months // 2, "splits": len(splits),
        "selection_tie_splits": int((in_ties > 1).sum()), "below_median_splits": below_median,
        "at_median_splits": int(splits.at_median.sum()), "pbo": below_median / len(splits),
        "negative_sharpe_splits": negative, "negative_sharpe_fraction": negative / len(splits)}
    return summary, splits


def run_overfitting(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    from tfm.data import read_result

    matrix, source = read_result(root, SELECTION_RETURNS)
    if source.get("test_interval") != TEST_INTERVAL or not source.get("attempt"):
        raise ValueError("Repite las secciones 47–48 con la matriz de desarrollo de 1950–1989.")
    candidates = matrix.loc[matrix.role.eq("candidate")].copy()
    candidates["excess"] = candidates.net_return - candidates.rf_return
    dsr, pbo, details = [], [], []
    for rule in RULES:
        excess = candidates.loc[candidates.rule.eq(rule)].pivot(index="period", columns="policy", values="excess")
        excess = excess.loc[:, list(FILTERS)]
        dsr.append(deflated_sharpe(excess).assign(rule=rule))
        summary, splits = combinatorial_pbo(excess)
        pbo.append({"rule": rule, **summary})
        details.append(splits.assign(rule=rule))
    return dict(zip(RESULT_NAMES, [pd.concat(dsr, ignore_index=True), pd.DataFrame(pbo),
                                  pd.concat(details, ignore_index=True)], strict=True)), {
        "attempt": datetime.now(timezone.utc).isoformat(), "source_attempt": source["attempt"],
        "test_interval": TEST_INTERVAL, "retained_candidates": list(FILTERS), "excess_return": "net_return_minus_rf",
        "pbo_blocks": PBO_BLOCKS, "pbo_selection": "highest_sharpe", "pbo_ties": "alphabetical_then_average_rank",
        "pbo_event": "below_median", "dsr_baseline": "expected_maximum_under_zero_sharpe",
        "dsr_count": "average_pearson_interpolation_rounded_up", "protocol": "docs/dsr_pbo.md"}
