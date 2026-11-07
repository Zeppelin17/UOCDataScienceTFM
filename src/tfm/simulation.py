"""Tres estrategias mensuales, con una cuenta explícita y supuestos comunes."""

import math

import pandas as pd

from tfm.sources.shiller import INSTRUMENT


STRATEGIES = {"buy_and_hold": "Comprar y mantener", "momentum": "Momentum", "reversal": "Reversión"}
WARNINGS = [
    "Aproximación histórica sobre precios medios de Shiller, no operaciones ejecutables.",
    "Dividendos D/12 reconstruidos; no se acredita disponibilidad histórica de cada revisión.",
    "Exposición objetivo mensual entre -1 y +1 sobre capital después de costes, sin margen intramensual; las reglas básicas usan -1, 0 o +1.",
    "El efectivo y el capital aportado a un corto reciben RF; los ingresos de la venta corta no reciben interés adicional.",
    "El préstamo se carga sobre el nominal inicial del corto, a tasa anual/12; tarifas hipotéticas.",
    "Dividendos de largos reinvertidos sin comisión separada; los cortos pagan dividendos y se reajustan mensualmente.",
    "Se cobran apertura, reajustes y liquidación final; no se aplican impuestos ni restricciones históricas de préstamo.",
    "Resultados de desarrollo 1927–1989, sin filtros de aprendizaje automático ni evaluación final.",
]


def validate_parameters(parameters: dict) -> None:
    required = {"initial_capital", "transaction_cost_rate", "annual_borrow_rate", "include_dividends"}
    if not isinstance(parameters, dict) or set(parameters) != required:
        raise ValueError("simulation requiere initial_capital, transaction_cost_rate, annual_borrow_rate e include_dividends")
    for key in required - {"include_dividends"}:
        value = parameters[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"simulation.{key} debe ser un número finito")
    if (parameters["initial_capital"] <= 0 or not 0 <= parameters["transaction_cost_rate"] < 1
            or parameters["annual_borrow_rate"] < 0 or type(parameters["include_dividends"]) is not bool):
        raise ValueError("Capital positivo, coste entre 0 y 1, préstamo no negativo e include_dividends booleano")


def _check_inputs(components: pd.DataFrame, signals: pd.DataFrame) -> None:
    required = {"asset", "period", "previous_period", "price_return", "dividend_return_approx", "rf_return"}
    signal_columns = {"asset", "basis", "decision_period", "target_period", "momentum_signal", "reversal_signal"}
    if components.empty or not required <= set(components) or not signal_columns <= set(signals):
        raise ValueError("Se necesitan componentes y señales completos para simular")
    months = pd.PeriodIndex(components.period, freq="M")
    periods = pd.period_range(months[0], months[-1], freq="M").astype(str).tolist()
    previous = (months - 1).astype(str).tolist()
    if (components.period.tolist() != periods or components.previous_period.tolist() != previous
            or signals.target_period.tolist() != periods or signals.decision_period.tolist() != previous):
        raise ValueError("Cada mes requiere su componente y la señal del mes anterior, sin huecos ni duplicados")
    if (not components.asset.eq(INSTRUMENT).all() or not signals.asset.eq(INSTRUMENT).all()
            or not signals.basis.eq("monthly_mean_price").all()):
        raise ValueError("Las estrategias requieren Shiller mensual sobre precios medios")
    for column in ("price_return", "dividend_return_approx", "rf_return"):
        values = components[column]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or values.isna().any() or not values.map(math.isfinite).all()):
            raise ValueError("Los componentes de rentabilidad deben ser numéricos y finitos")
    if (components.price_return.le(-1).any() or components.dividend_return_approx.lt(0).any()
            or components.rf_return.le(-1).any()):
        raise ValueError("Los componentes contienen rentabilidades incompatibles con el protocolo")
    for column, allowed in (("momentum_signal", [0, 1]), ("reversal_signal", [-1, 0, 1])):
        values = signals[column]
        if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                or values.isna().any() or not values.isin(allowed).all()):
            raise ValueError("Las señales deben tener posiciones válidas; un dato ausente no equivale a efectivo")


def simulate_baselines(components: pd.DataFrame, signals: pd.DataFrame, parameters: dict, *,
                       exposure_scale: pd.Series | None = None,
                       reset_each_month: bool = False) -> pd.DataFrame:
    """No descargar ni guardar; decidir exclusivamente con las señales anteriores.

    El nominal se ajusta a q * capital después de la comisión. Resolver el
    nominal negociado evita financiar la comisión con capital inexistente.
    Un corto conserva su nominal marcado a precio para medir el reajuste siguiente.
    reset_each_month abre desde efectivo y liquida cada mes para etiquetar
    operaciones aisladas; el comportamiento habitual conserva posiciones.
    """
    validate_parameters(parameters)
    _check_inputs(components, signals)
    if type(reset_each_month) is not bool:
        raise ValueError("reset_each_month debe ser booleano")
    if exposure_scale is not None:
        if (not isinstance(exposure_scale, pd.Series)
                or exposure_scale.index.tolist() != components.period.tolist()
                or not pd.api.types.is_numeric_dtype(exposure_scale)
                or pd.api.types.is_bool_dtype(exposure_scale) or exposure_scale.isna().any()
                or not exposure_scale.map(math.isfinite).all()
                or not exposure_scale.between(0, 1).all()):
            raise ValueError("La escala requiere un valor entre 0 y 1 para cada mes objetivo, en el mismo orden")
    fee = float(parameters["transaction_cost_rate"])
    borrow_monthly = float(parameters["annual_borrow_rate"]) / 12
    records = []
    for strategy in STRATEGIES:
        equity = float(parameters["initial_capital"])
        carried_notional = 0.0
        for i, row in enumerate(components.itertuples(index=False)):
            if reset_each_month:
                equity = float(parameters["initial_capital"])
                carried_notional = 0.0
            q = 1 if strategy == "buy_and_hold" else int(signals.iloc[i][f"{strategy}_signal"])
            if exposure_scale is not None:
                q *= float(exposure_scale.iloc[i])
            start = equity
            desired_trade = q * start - carried_notional
            direction = 1 if desired_trade > 0 else -1 if desired_trade < 0 else 0
            traded = abs(desired_trade) / (1 + direction * q * fee)
            transaction_cost = fee * traded
            invested = start - transaction_cost
            if not math.isfinite(invested) or invested <= 0:
                raise ValueError(f"{STRATEGIES[strategy]} sin capital tras negociar en {row.period}")
            dividend_return = float(row.dividend_return_approx) if parameters["include_dividends"] else 0.0
            price_pnl = q * invested * float(row.price_return)
            dividend_pnl = q * invested * dividend_return
            cash_interest = invested * (1 - max(q, 0)) * float(row.rf_return)
            borrow_cost = invested * abs(q) * borrow_monthly if q < 0 else 0.0
            before_close = invested + price_pnl + dividend_pnl + cash_interest - borrow_cost
            # Largo: reinversión del dividendo sin comisión separada. Corto:
            # el dividendo sale de efectivo; el nominal cambia solo con el precio.
            if q == 1:
                end_notional = before_close
            elif q > 0:
                end_notional = q * invested + price_pnl + dividend_pnl
            else:
                end_notional = q * invested * (1 + row.price_return) if q < 0 else 0.0
            close_position = reset_each_month or i == len(components) - 1
            liquidation_notional = abs(end_notional) if close_position else 0.0
            liquidation_cost = fee * liquidation_notional
            equity = before_close - liquidation_cost
            if not math.isfinite(equity) or equity <= 0:
                raise ValueError(f"{STRATEGIES[strategy]} insolvente en {row.period}; la simulación se detiene")
            carried_notional = 0.0 if close_position else end_notional
            records.append({
                "strategy": strategy, "period": row.period, "decision_period": row.previous_period,
                "position": q, "capital_start": start, "capital_after_trading": invested,
                "trade_notional": traded, "transaction_cost": transaction_cost,
                "price_return": float(row.price_return), "dividend_return_used": dividend_return,
                "rf_return": float(row.rf_return), "price_pnl": price_pnl, "dividend_pnl": dividend_pnl,
                "cash_interest": cash_interest, "borrow_cost": borrow_cost,
                "capital_before_liquidation": before_close, "liquidation_notional": liquidation_notional,
                "liquidation_cost": liquidation_cost, "asset_notional_end": carried_notional,
                "capital_end": equity, "net_return": equity / start - 1,
                "turnover": (traded + liquidation_notional) / start,
            })
    result = pd.DataFrame(records)
    numeric = result.drop(columns=["strategy", "period", "decision_period"])
    if not all(numeric[column].map(math.isfinite).all() for column in numeric):
        raise ValueError("La simulación produjo un resultado no finito")
    return result


def summarize_baselines(table: pd.DataFrame, parameters: dict, *, strategies: dict | None = None) -> list[dict]:
    """Sharpe sobre exceso mensual, drawdown incluyendo el capital inicial."""
    initial = float(parameters["initial_capital"])
    summaries = []
    for strategy, label in (STRATEGIES if strategies is None else strategies).items():
        rows = table.loc[table.strategy.eq(strategy)]
        capital = pd.Series([initial, *rows.capital_end.tolist()])
        drawdown = capital / capital.cummax() - 1
        excess = rows.net_return - rows.rf_return
        excess_std = float(excess.std(ddof=1))
        volatility = float(rows.net_return.std(ddof=1)) if len(rows) > 1 else 0.0
        summaries.append({
            "strategy": strategy, "label": label, "months": len(rows),
            "capital_final": float(capital.iloc[-1]),
            "total_return": float(capital.iloc[-1] / initial - 1),
            "annualized_return": math.expm1(math.log(capital.iloc[-1] / initial) * 12 / len(rows)),
            "annualized_volatility": volatility * math.sqrt(12),
            "sharpe": float(excess.mean() / excess_std * math.sqrt(12)) if excess_std > 1e-12 else None,
            "max_drawdown": float(drawdown.min()),
            "annualized_turnover": float(rows.turnover.sum() * 12 / len(rows)),
            "transaction_cost_total": float(rows.transaction_cost.sum() + rows.liquidation_cost.sum()),
            "borrow_cost_total": float(rows.borrow_cost.sum()),
        })
    return summaries
