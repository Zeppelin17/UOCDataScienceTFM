"""Cribado temporal descriptivo de 1.B; sin selección automática ni entrenamiento.

Protocolo: docs/hipotesis_y_cribado.md. Fórmulas propias de OLS/Newey–West
(Bartlett, sin corrección de muestra pequeña), BH y Holm. Jansen, capítulos 7–8,
aporta organización; no se copia su IC transversal ni sus permutaciones.
"""

import math

import numpy as np
import pandas as pd

from tfm.diagnostics import START, END
from tfm.features import FEATURE_COLUMNS
from tfm.simulation import simulate_baselines
from tfm.sources.shiller import INSTRUMENT


MIN_HISTORY = 36
HAC_LAGS = 6
BH_ALPHA = 0.10
HOLM_ALPHA = 0.05
MIN_SHIFT = 36
RULES = ("momentum", "reversal")
POSITIVE_MOMENTUM = {"momentum_12_1", "market_return_24m", "distance_ma_12m",
                     "drawdown_12m", "industry_breadth_12m"}
SUBPERIODS = (("1927-01", "1942-12"), ("1943-01", "1958-12"),
              ("1959-01", "1974-12"), ("1975-01", "1989-12"))
RESULT_NAMES = ("screening_monthly", "screening_tests", "screening_terciles",
                "screening_stability", "screening_shadows")


def transform_features(features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Estadísticos de x anteriores a cada fila; nunca usar su valor actual ni y."""
    months = pd.period_range(START, END, freq="M")
    required = {"asset", "target_period", "decision_period", "price_source_period",
                "context_source_period", *FEATURE_COLUMNS}
    if (not required <= set(features) or features.target_period.tolist() != months.astype(str).tolist()
            or features.decision_period.tolist() != (months - 1).astype(str).tolist()
            or features.price_source_period.tolist() != (months - 1).astype(str).tolist()
            or features.context_source_period.tolist() != (months - 2).astype(str).tolist()
            or not features.asset.eq(INSTRUMENT).all()):
        raise ValueError("Se requieren características alineadas de 1927–1989; ejecuta el notebook 07.")
    result = features[["asset", "target_period", "decision_period", "price_source_period",
                       "context_source_period"]].reset_index(drop=True).copy()
    reasons = [[] for _ in months]
    for name in FEATURE_COLUMNS:
        series = features[name]
        if (not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series)
                or not series.dropna().map(math.isfinite).all()):
            raise ValueError(f"Característica no numérica o no finita: {name}")
        valid = series.notna().to_numpy()
        if not valid.any() or not valid[np.flatnonzero(valid)[0]:].all():
            raise ValueError(f"Sin datos o con huecos interiores en {name}; revisa el notebook 07.")
        values = series.to_numpy(dtype=float, na_value=np.nan)
        z = np.full(len(values), np.nan)
        terciles = pd.array([pd.NA] * len(values), dtype="Int8")
        for i, value in enumerate(values):
            history = values[:i]
            history = history[np.isfinite(history)]
            reason = None
            if not math.isfinite(value):
                reason = "missing_current"
            elif len(history) < MIN_HISTORY:
                reason = "history_warmup"
            else:
                lower, upper = np.quantile(history, [.01, .99], method="linear")
                clipped = np.clip(history, lower, upper)
                deviation = clipped.std(ddof=1)
                if deviation <= np.finfo(float).eps * max(1.0, abs(float(clipped.mean()))):
                    reason = "constant_history"
                else:
                    z[i] = (np.clip(value, lower, upper) - clipped.mean()) / deviation
                # Los cortes se calculan en x original, con exactamente el mismo pasado.
                low, high = np.quantile(history, [1/3, 2/3], method="linear")
                terciles[i] = (1 if value < low else 3 if value > high else 2) if low == high else (
                    1 if value <= low else 3 if value > high else 2)
            if reason:
                reasons[i].append(f"{name}:{reason}")
        result[f"z_{name}"] = z
        result[f"tercile_{name}"] = terciles
    result["screening_ready"] = result[[f"z_{f}" for f in FEATURE_COLUMNS]].notna().all(axis=1)
    result["exclusion_reason"] = ["; ".join(items) for items in reasons]
    report = {
        "calendar_months": len(result), "min_history": MIN_HISTORY,
        "excluded_targets": [{"target_period": str(month), "reasons": items}
                             for month, items in zip(months, reasons) if items],
    }
    return result, report


def build_screening_monthly(features: pd.DataFrame, components: pd.DataFrame,
                             signals: pd.DataFrame, parameters: dict) -> tuple[pd.DataFrame, dict]:
    """Simular todo el calendario antes del calentamiento y conservar sus dos reglas."""
    transformed, report = transform_features(features)
    if components.period.tolist() != transformed.target_period.tolist():
        raise ValueError("Componentes y características deben cubrir el mismo calendario 1927–1989.")
    ledger = simulate_baselines(components, signals, parameters)
    ledger = ledger.loc[ledger.strategy.isin(RULES), ["strategy", "period", "decision_period", "position",
                                                    "net_return", "rf_return"]].rename(columns={"period": "target_period"})
    ledger["asset"] = INSTRUMENT
    ledger["has_signal"] = ledger.position.ne(0)
    ledger["anomaly_return"] = ledger.net_return - ledger.rf_return
    table = ledger.merge(transformed, on=["asset", "target_period", "decision_period"],
                         how="left", validate="many_to_one")
    common = transformed.loc[transformed.screening_ready, "target_period"]
    if len(common) < 2 * MIN_SHIFT + 1:
        raise ValueError("No hay un tramo común suficiente para las sombras de 36 meses; revisa la preparación.")
    if common.tolist() != pd.period_range(common.iloc[0], common.iloc[-1], freq="M").astype(str).tolist():
        raise ValueError("Hay huecos interiores en la muestra común; no se comprime el calendario.")
    report.update({"common_months": len(common), "first_target": common.iloc[0], "last_target": common.iloc[-1],
                   "response": "continuous_unfiltered_net_return_minus_rf", "parameters": parameters,
                   "feature_columns": FEATURE_COLUMNS, "hac_lags": HAC_LAGS,
                   "hac_small_sample_correction": False, "family_size": 20,
                   "multiple_testing": {
                       "primary": {"method": "BH", "adjusted_p_threshold": BH_ALPHA, "comparison": "<"},
                       "secondary": {"method": "Holm", "adjusted_p_threshold": HOLM_ALPHA, "comparison": "<="},
                       "family": "all ten features and both rules jointly",
                       "non_estimable_p_for_adjustment": 1.0,
                       "revision": "2026-11-14; tutor recommendation after initial Holm analysis",
                   },
                   "min_circular_shift_months": MIN_SHIFT,
                   "transform": "past-only expanding 1/99 winsorization and sample z-score; linear quantiles",
                   "subperiods": [list(pair) for pair in SUBPERIODS]})
    return table, report


def hac_regression(x, y) -> dict:
    """OLS con intercepto y varianza HAC de la pendiente; no eliminar filas ausentes.

    Con x centrada, Var(b) = [sum(u²) + 2 sum_l w_l sum_t(u_t u_(t-l))] / Sxx²,
    donde u_t = (x_t - media(x)) * residuo_t y w_l = 1 - l/(L+1).
    No se aplica n/(n-2). Los p son normales asintóticos, no t de Student.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if (x.ndim != 1 or y.shape != x.shape or not np.isfinite(x).all() or not np.isfinite(y).all()):
        raise ValueError("La regresión requiere dos series finitas alineadas, sin eliminar meses.")
    result = {"months": len(x), "intercept": None, "slope": None, "standard_error": None,
              "t_hac": None, "p_value": None, "estimable": False, "reason": "insufficient_months"}
    if len(x) <= HAC_LAGS + 2:
        return result
    centered = x - x.mean()
    sxx = float(centered @ centered)
    if sxx <= np.finfo(float).eps * len(x) * max(1.0, float(np.max(np.abs(x))) ** 2):
        return {**result, "reason": "constant_predictor"}
    slope = float(centered @ (y - y.mean()) / sxx)
    intercept = float(y.mean() - slope * x.mean())
    residual = y - intercept - slope * x
    result.update(intercept=intercept, slope=slope)
    if np.max(np.abs(residual)) <= 32 * np.finfo(float).eps * max(1.0, float(np.max(np.abs(y)))):
        return {**result, "reason": "zero_residual_variance"}
    scores = centered * residual
    meat = float(scores @ scores)
    for lag in range(1, HAC_LAGS + 1):
        meat += 2 * (1 - lag / (HAC_LAGS + 1)) * float(scores[lag:] @ scores[:-lag])
    if meat <= 0:
        return {**result, "reason": "non_positive_hac_variance"}
    se = math.sqrt(meat) / sxx
    statistic = slope / se
    return {**result, "standard_error": se, "t_hac": statistic,
            "p_value": math.erfc(abs(statistic) / math.sqrt(2)), "estimable": True, "reason": "ok"}


def holm_adjust(p_values) -> np.ndarray:
    """Ajuste step-down en orden original, conservando toda la familia."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Holm requiere valores p entre 0 y 1 para toda la familia.")
    order = np.argsort(p, kind="stable")
    adjusted = np.minimum(1.0, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    result = np.empty(len(p))
    result[order] = adjusted
    return result


def bh_adjust(p_values) -> np.ndarray:
    """Benjamini–Hochberg step-up; devolver p ajustados en el orden original."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("BH requiere valores p entre 0 y 1 para toda la familia.")
    order = np.argsort(p, kind="stable")
    scaled = p[order] * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum(1.0, np.minimum.accumulate(scaled[::-1])[::-1])
    result = np.empty(len(p))
    result[order] = adjusted
    return result


def _common_arrays(monthly: pd.DataFrame):
    """Impedir que las sombras cuenten filas separadas como meses consecutivos."""
    rows = monthly.loc[monthly.screening_ready].copy()
    by_rule = [rows.loc[rows.strategy.eq(rule)] for rule in RULES]
    periods = by_rule[0].target_period.tolist()
    if (not periods or len(periods) < 2 * MIN_SHIFT + 1
            or periods != pd.period_range(periods[0], periods[-1], freq="M").astype(str).tolist()
            or by_rule[1].target_period.tolist() != periods
            or set(rows.strategy) != set(RULES)):
        raise ValueError("Las dos reglas necesitan el mismo tramo mensual continuo para el cribado.")
    columns = [f"z_{f}" for f in FEATURE_COLUMNS]
    x = by_rule[0][columns].to_numpy(dtype=float)
    if (not np.isfinite(x).all() or not np.array_equal(x, by_rule[1][columns].to_numpy(dtype=float))):
        raise ValueError("Las dos reglas deben tener las mismas características finitas por fecha.")
    y = [part.anomaly_return.to_numpy(dtype=float) for part in by_rule]
    if not all(np.isfinite(values).all() for values in y):
        raise ValueError("Faltan resultados en la muestra común; no se eliminan meses.")
    return rows, by_rule, x, y


def screen_relationships(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Veinte contrastes: BH principal, Holm adicional y sombras separadas."""
    _, _, x, targets = _common_arrays(monthly)
    records = []
    for rule, y in zip(RULES, targets):
        for j, feature in enumerate(FEATURE_COLUMNS):
            records.append({"strategy": rule, "feature": feature,
                            "expected_sign": "+" if rule == "momentum" and feature in POSITIVE_MOMENTUM else "unspecified",
                            **hac_regression(x[:, j], y)})
    tests = pd.DataFrame(records)
    family_p = tests.p_value.fillna(1).to_numpy()
    tests["p_bh"] = bh_adjust(family_p)
    tests["p_holm"] = holm_adjust(family_p)
    tests["passes_bh"] = tests.estimable & tests.p_bh.lt(BH_ALPHA)
    tests["passes_holm"] = tests.estimable & tests.p_holm.le(HOLM_ALPHA)
    shadows = []
    for shift in range(MIN_SHIFT, len(x) - MIN_SHIFT + 1):
        moved = np.roll(x, shift, axis=0)  # Mismo desplazamiento para las diez columnas y ambas reglas.
        stats = [hac_regression(moved[:, j], y)["t_hac"] for y in targets for j in range(len(FEATURE_COLUMNS))]
        valid = [abs(value) for value in stats if value is not None and math.isfinite(value)]
        shadows.append({"shift_months": shift, "circular_distance_months": min(shift, len(x) - shift),
                        "max_abs_t_hac": max(valid) if len(valid) == len(tests) else None, "estimable_tests": len(valid)})
    shadows = pd.DataFrame(shadows)
    # Exigir la familia completa en cada sombra; no descartar desplazamientos incompletos.
    usable = shadows.max_abs_t_hac.notna().all()
    threshold = float(np.quantile(shadows.max_abs_t_hac, .95, method="higher")) if usable else None
    tests["shadow_threshold_95"] = threshold
    tests["exceeds_shadows"] = pd.array(
        [abs(row.t_hac) > threshold if row.estimable and threshold is not None else pd.NA
         for row in tests.itertuples()], dtype="boolean")
    status, directions = [], []
    for row in tests.itertuples():
        if not row.estimable:
            value = "not_estimable"
        elif not row.passes_bh:
            value = "no_bh_evidence"
        elif row.passes_holm:
            value = "bh_and_holm"
        else:
            value = "bh_only"
        status.append(value)
        directions.append("not_estimable" if not row.estimable else
                          "exploratory" if row.expected_sign == "unspecified" else
                          "supports_expected_sign" if row.slope > 0 else "does_not_support_expected_sign")
    tests["evidence_status"] = status
    tests["direction_status"] = directions
    return tests, shadows, {"shadow_count": len(shadows), "shadow_threshold_95": threshold,
                            "shadow_comparison_available": bool(usable),
                            "shadow_unavailable_count": int(shadows.max_abs_t_hac.isna().sum())}


def describe_regimes(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Terciles y pendientes por tramos; sin contrastes extra ni reiniciar carteras."""
    _, by_rule, _, _ = _common_arrays(monthly)
    terciles, stability = [], []
    for rule, rows in zip(RULES, by_rule):
        for feature in FEATURE_COLUMNS:
            for tercile in (1, 2, 3):
                part = rows.loc[rows[f"tercile_{feature}"].eq(tercile)]
                excess = part.anomaly_return
                deviation = float(excess.std(ddof=1)) if len(part) > 1 else 0.0
                terciles.append({"strategy": rule, "feature": feature, "tercile": tercile,
                                 "months": len(part), "signal_months": int(part.has_signal.sum()),
                                 "signal_fraction": float(part.has_signal.mean()) if len(part) else None,
                                 "mean_excess_return": float(excess.mean()) if len(part) else None,
                                 "annualized_conditional_sharpe": float(excess.mean() / deviation * math.sqrt(12)) if deviation > 1e-12 else None})
            for start, end in SUBPERIODS:
                part = rows.loc[rows.target_period.between(start, end)]
                fit = hac_regression(part[f"z_{feature}"], part.anomaly_return)
                stability.append({"strategy": rule, "feature": feature, "subperiod_start": start,
                                  "subperiod_end": end, "first_observed_target": part.target_period.min() if len(part) else None,
                                  "last_observed_target": part.target_period.max() if len(part) else None,
                                  "months": len(part), "slope": fit["slope"], "reason": fit["reason"]})
    return pd.DataFrame(terciles), pd.DataFrame(stability)
