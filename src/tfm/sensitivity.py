"""Escenarios declarados de costes y dividendos, sin optimizar las reglas."""

import pandas as pd

from tfm.simulation import simulate_baselines, summarize_baselines, validate_parameters


TRANSACTION_RATES = (0.0, 0.001, 0.0025, 0.005)
BORROW_RATES = (0.0025, 0.01, 0.03)


def sensitivity_scenarios(parameters: dict) -> list[dict]:
    """Cambiar un supuesto cada vez respecto al escenario declarado en el notebook.

    El central aparece una sola vez. Si se configura una tarifa distinta de
    las previstas, se conserva también: no se descarta ni se escoge por resultado.
    """
    validate_parameters(parameters)
    scenarios = [{"scenario": "central", "scenario_label": "Central (configuración)",
                  "changed_assumption": "none", "parameters": dict(parameters)}]
    for key, rates, prefix, label in (
        ("transaction_cost_rate", TRANSACTION_RATES, "transaction", "Negociación"),
        ("annual_borrow_rate", BORROW_RATES, "borrow", "Préstamo anual"),
    ):
        for rate in rates:
            if rate != parameters[key]:
                scenarios.append({"scenario": f"{prefix}_{rate:g}",
                                  "scenario_label": f"{label} {100 * rate:g} %",
                                  "changed_assumption": key,
                                  "parameters": {**parameters, key: rate}})
    included = not parameters["include_dividends"]
    scenarios.append({"scenario": "dividends_toggle",
                      "scenario_label": "Con dividendos aprox." if included else "Sin dividendos",
                      "changed_assumption": "include_dividends",
                      "parameters": {**parameters, "include_dividends": included}})
    return scenarios


def run_sensitivities(components: pd.DataFrame, signals: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """Reutilizar el simulador y las mismas señales/fechas en todos los casos.

    Solo se conserva el resumen de cada cuenta. Una simulación inválida
    detiene la comparación completa, sin eliminar el escenario desfavorable.
    """
    records = []
    central = {}
    for scenario in sensitivity_scenarios(parameters):
        params = scenario["parameters"]
        try:
            ledger = simulate_baselines(components, signals, params)
            summaries = summarize_baselines(ledger, params)
        except ValueError as exc:
            raise ValueError(f"{scenario['scenario_label']}: {exc}. No se han omitido escenarios.") from exc
        for summary in summaries:
            if scenario["scenario"] == "central":
                central[summary["strategy"]] = summary["annualized_return"]
            records.append({"scenario": scenario["scenario"], "scenario_label": scenario["scenario_label"],
                            "changed_assumption": scenario["changed_assumption"], **params, **summary,
                            "annualized_return_delta": summary["annualized_return"] - central[summary["strategy"]]})
    return pd.DataFrame(records)
