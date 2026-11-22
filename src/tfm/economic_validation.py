"""Contraste de Sharpe e inventario de variantes del desarrollo."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfm.clustered_mda import VARIANT as MDA_VARIANT
from tfm.diagnostics import END, START
from tfm.economics import ACCOUNT_LABELS, DECISION_POLICY, RESULT_NAMES as ECONOMIC_RESULTS
from tfm.forest import VARIANTS as FOREST_VARIANTS
from tfm.forest_economics import ACCOUNT as FOREST_ACCOUNT, REPORT_LABELS, RESULT_NAMES as FOREST_RESULTS
from tfm.logistic import VARIANT as ALL_FEATURES_VARIANT
from tfm.screening import RULES
from tfm.walk_forward import FIRST_TEST_YEAR, INTERACTION_VARIANT, LAST_TEST_YEAR, REGIME_VARIANT, VARIANT


TEST_INTERVAL = [f"{FIRST_TEST_YEAR}-01", f"{LAST_TEST_YEAR}-12"]
SHARPE_REFERENCES = ("momentum", "momentum_bear", "momentum_volatility")
BLOCK_MONTHS = 12
BOOTSTRAP_REPETITIONS = 5000
CONFIDENCE = .95
SEED = 42
LINEAR_VARIANTS = {"M1": VARIANT, "M2": REGIME_VARIANT, "M3": INTERACTION_VARIANT}
CANDIDATE_LABELS = {v: f"L2_{m}" for m, v in LINEAR_VARIANTS.items()}
CANDIDATE_LABELS.update({ALL_FEATURES_VARIANT: "Logística · diez variables (CPCV)",
                         MDA_VARIANT: "Logística · Clustered MDA"})


def sharpe_and_influence(excess: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sharpe anualizado y contribuciones centradas para su error estándar."""
    n = excess.shape[-2]
    mean = excess.mean(axis=-2, keepdims=True)
    centered = excess - mean
    variance = (centered**2).mean(axis=-2, keepdims=True)
    if (variance <= 1e-24).any():
        raise ValueError("El Sharpe requiere variación en los retornos sobre el efectivo.")
    scale = np.sqrt(12 * (n - 1) / n)
    sharpe = scale * mean / np.sqrt(variance)
    influence = (scale * centered / np.sqrt(variance)
                 - sharpe * (centered**2 - variance) / (2 * variance))
    return sharpe.squeeze(axis=-2), influence


def paired_sharpe_test(excess: np.ndarray, *, block_months: int = BLOCK_MONTHS,
                       repetitions: int = BOOTSTRAP_REPETITIONS) -> dict:
    """Bootstrap circular studentizado de la diferencia de Sharpe (Ledoit–Wolf adaptado)."""
    excess = np.asarray(excess, dtype=float)
    if (excess.ndim != 2 or excess.shape[1] != 2 or not np.isfinite(excess).all()
            or block_months < 2 or len(excess) % block_months or len(excess) // block_months < 2
            or repetitions < 1):
        raise ValueError("Se requieren dos series finitas emparejadas y bloques completos.")
    n = len(excess)
    sharpe, influence = sharpe_and_influence(excess)
    delta = float(sharpe[0] - sharpe[1])
    score = influence[:, 0] - influence[:, 1]
    # Error HAC de Bartlett con pesos fijados por la longitud del bloque.
    long_run_variance = score @ score / n
    for lag in range(1, block_months):
        long_run_variance += 2 * (1 - lag / block_months) * (score[lag:] @ score[:-lag]) / n
    if long_run_variance <= 1e-24:
        raise ValueError("La diferencia de Sharpe no tiene un error estándar estimable.")
    standard_error = np.sqrt(long_run_variance / n)

    rng = np.random.default_rng(SEED)
    statistics = []
    for first in range(0, repetitions, 250):
        size = min(250, repetitions - first)
        starts = rng.integers(n, size=(size, n // block_months, 1))
        indices = (starts + np.arange(block_months)) % n
        draws = excess[indices.reshape(size, n)]
        # Cada repetición conserva las parejas y permite el empalme circular.
        draw_sharpe, draw_influence = sharpe_and_influence(draws)
        draw_score = (draw_influence[..., 0] - draw_influence[..., 1]).reshape(indices.shape)
        block_sums = draw_score.sum(axis=-1)
        draw_error = np.sqrt((block_sums**2).mean(axis=-1) / (n * block_months))
        if (draw_error <= 1e-12).any():
            raise ValueError("Hay réplicas con un error estándar de la diferencia no estimable.")
        statistics.extend(np.abs(draw_sharpe[:, 0] - draw_sharpe[:, 1] - delta) / draw_error)
    statistics = np.asarray(statistics)
    critical_value = np.quantile(statistics, CONFIDENCE, method="higher")
    radius = critical_value * standard_error
    count = np.count_nonzero(statistics >= abs(delta) / standard_error)
    return {"months": n, "sharpe_candidate": float(sharpe[0]), "sharpe_reference": float(sharpe[1]),
            "sharpe_difference": delta, "ci_low": float(delta - radius), "ci_high": float(delta + radius),
            "p_value": (int(count) + 1) / (repetitions + 1)}


def aligned_accounts(accounts: pd.DataFrame, expected: set[str]) -> tuple[pd.DataFrame, pd.Series]:
    """Exigir los mismos meses y efectivo para todas las cuentas guardadas."""
    calendar = pd.period_range(*TEST_INTERVAL, freq="M").astype(str).tolist()
    if set(accounts.strategy) != expected or accounts.duplicated(["period", "strategy"]).any():
        raise ValueError("Las cuentas de desarrollo deben estar completas y sin duplicados.")
    returns = accounts.pivot(index="period", columns="strategy", values="net_return")
    risk_free = accounts.pivot(index="period", columns="strategy", values="rf_return")
    if (returns.index.tolist() != calendar or not np.isfinite(returns.to_numpy(dtype=float)).all()
            or not np.isfinite(risk_free.to_numpy(dtype=float)).all()
            or not risk_free.eq(risk_free.iloc[:, 0], axis=0).all().all()):
        raise ValueError("Se requieren retornos completos de 1950–1989 y el mismo efectivo por mes.")
    return returns, risk_free.iloc[:, 0]


def load_development_accounts(root: Path) -> tuple[pd.DataFrame, pd.Series, dict]:
    from tfm.data import read_result

    accounts, linear = read_result(root, ECONOMIC_RESULTS[1])
    if (linear.get("test_interval") != TEST_INTERVAL or linear.get("experiment_status") != "completed"
            or linear.get("decision_policy") != DECISION_POLICY or not linear.get("attempt")):
        raise ValueError("Ejecuta las secciones 19–22 del notebook 14 para preparar las cuentas de desarrollo.")
    returns, risk_free = aligned_accounts(accounts, set(ACCOUNT_LABELS))
    attempts = linear["source_attempts"]
    published = {(variant, rule): (f"{rule}_{model.lower()}", attempts["M0_M1" if model == "M1" else model])
                 for model, variant in LINEAR_VARIANTS.items() for rule in RULES}
    if (root / "data/processed" / f"{FOREST_RESULTS[1]}.parquet").is_file():
        forest_accounts, forest = read_result(root, FOREST_RESULTS[1])
        if (forest.get("test_interval") != TEST_INTERVAL or forest.get("experiment_status") != "completed"
                or forest.get("decision_policy") != DECISION_POLICY or forest.get("model") != "RF_M1"
                or forest.get("rule") != "reversal" or forest.get("parameters") != linear["parameters"]
                or forest.get("source_attempts", {}).get("economic_references") != linear["attempt"]):
            raise ValueError("Ejecuta las secciones 40–41 del notebook 14 con las cuentas de desarrollo actuales.")
        forest_returns, forest_risk_free = aligned_accounts(forest_accounts, set(REPORT_LABELS))
        references = list(forest_returns.columns.drop(FOREST_ACCOUNT))
        if (not np.array_equal(forest_risk_free, risk_free)
                or not np.array_equal(forest_returns[references], returns[references])):
            raise ValueError("Las referencias del bosque deben coincidir con las cuentas de desarrollo.")
        published[FOREST_VARIANTS["RF_M1"], "reversal"] = (FOREST_ACCOUNT, forest["source_attempts"]["forest"])
    return returns, risk_free, published


def read_candidate_attempts(root: Path) -> pd.DataFrame:
    """Recoger los intentos de variantes originales por regla a partir del registro."""
    records = []
    histories = root / "outputs/experiments"
    for path in sorted(histories.glob("*_trials.jsonl")):
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Registro JSONL incompleto en {path.name}, línea {number}.") from exc
                if row.get("candidate_configurations_per_rule") != 1:
                    continue
                chronological = (row.get("test_interval") == TEST_INTERVAL
                                 or row.get("test_years") == [FIRST_TEST_YEAR, LAST_TEST_YEAR])
                cpcv = row.get("development") == [START, END] and path.stem in {
                    "logistic_trials", "clustered_mda_trials"}
                if not (chronological or cpcv):
                    continue
                variant = row["variant"]
                label = (row.get("candidate") or row.get("subset_model") or CANDIDATE_LABELS.get(variant)
                         or ("EBM_M1" if path.stem == "ebm_trials" else variant))
                records.extend({"variant": variant, "candidate": label, "rule": rule, "source": path.name,
                    "status": row["status"], "attempt": row["attempt"],
                    "batch_attempt": row.get("batch_attempt"), "chronological": chronological}
                    for rule in row["strategies"])
    columns = ["variant", "candidate", "rule", "source", "status", "attempt", "batch_attempt", "chronological"]
    return pd.DataFrame(records, columns=columns).drop_duplicates(["variant", "rule", "attempt"], keep="last")


def build_candidate_inventory(attempts: pd.DataFrame, published: dict) -> pd.DataFrame:
    """Mostrar qué serie se publicó y qué faltaría preparar para cada variante."""
    records = []
    for (variant, rule), events in attempts.sort_values("attempt").groupby(["variant", "rule"], sort=False):
        latest = events.iloc[-1]
        completed = events.loc[events.status.eq("completed")]
        account, origin = published.get((variant, rule), (None, None))
        identified = (account is not None and
                      (completed.attempt.eq(origin) | completed.batch_attempt.eq(origin)).any())
        if identified:
            need = "Retornos disponibles"
        elif account is not None:
            need = "Revisar el intento de origen"
        elif completed.empty:
            need = "Sin intento completado"
        elif completed.chronological.any():
            need = ("Reproducir el recorrido del bloque y simular"
                    if latest.source == "walk_forward_block_trials.jsonl" else "Simular cuenta walk-forward")
        else:
            need = "Preparar recorrido walk-forward y simular"
        same_inputs = ("Logística de diez variables del recorrido por bloques"
                       if variant == ALL_FEATURES_VARIANT else None)
        records.append({"rule": rule, "candidate": latest.candidate, "variant": variant, "source": latest.source,
            "attempts": len(events), "completed": len(completed), "latest_status": latest.status,
            "account": account, "source_attempt": origin, "next_step": need, "same_inputs": same_inputs})
    columns = ["rule", "candidate", "variant", "source", "attempts", "completed", "latest_status",
               "account", "source_attempt", "next_step", "same_inputs"]
    return pd.DataFrame(records, columns=columns).sort_values(["rule", "next_step", "candidate"], ignore_index=True)


def run_economic_validation(root: Path) -> dict[str, pd.DataFrame]:
    returns, risk_free, published = load_development_accounts(root)
    excess = returns.sub(risk_free, axis=0)
    comparisons, decades = [], []
    for reference in SHARPE_REFERENCES:
        pair = excess[["momentum_m1", reference]]
        label = ACCOUNT_LABELS[reference]
        comparisons.append({"reference": label, **paired_sharpe_test(pair.to_numpy())})
        for start in range(FIRST_TEST_YEAR, LAST_TEST_YEAR + 1, 10):
            years = pair.loc[f"{start}-01":f"{start + 9}-12"]
            sharpe, _ = sharpe_and_influence(years.to_numpy())
            decades.append({"reference": label, "decade": start, "months": len(years),
                "sharpe_candidate": sharpe[0], "sharpe_reference": sharpe[1],
                "sharpe_difference": sharpe[0] - sharpe[1]})
    return {"comparisons": pd.DataFrame(comparisons), "decades": pd.DataFrame(decades),
            "inventory": build_candidate_inventory(read_candidate_attempts(root), published)}
