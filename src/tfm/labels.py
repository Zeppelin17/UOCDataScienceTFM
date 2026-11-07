"""Etiquetas mensuales de operaciones aisladas frente al efectivo.

Referencia de diseño: Jansen, capítulo 7, 03_label_methods.py, revisión
91c903e71c1d0f1b9015f18551fadbb60bcad132. Implementación propia sobre nuestro
simulador: se incorporan dividendos, RF, préstamo y costes, sin copiar su código.
"""

import pandas as pd

from tfm.diagnostics import START, END
from tfm.simulation import simulate_baselines
from tfm.sources.shiller import INSTRUMENT


LABEL_TOLERANCE = 1e-12  # Retorno decimal; solo evita clasificar ruido numérico como ganancia.
SENSITIVITY_NAME = "no_transaction_cost_in_label"


def build_monthly_labels(components: pd.DataFrame, signals: pd.DataFrame,
                         parameters: dict) -> pd.DataFrame:
    """Conservar el calendario; efectivo sin operación recibe etiqueta ausente.

    y=1 si el retorno neto aislado supera RF en más de LABEL_TOLERANCE; y=0
    si no. El coste de negociación se elimina únicamente en la sensibilidad,
    conservando dividendos y préstamo. No se utiliza la etiqueta para cambiar
    el umbral ni la convención de la evaluación económica futura.
    """
    if ("period" not in components or components.empty
            or not components.period.between(START, END).all()):
        raise ValueError("El etiquetado se limita al desarrollo 1927–1989")
    central = simulate_baselines(components, signals, parameters, reset_each_month=True)
    alternative = simulate_baselines(components, signals,
                                     {**parameters, "transaction_cost_rate": 0.0},
                                     reset_each_month=True)
    central = central.loc[central.strategy.ne("buy_and_hold")].reset_index(drop=True)
    alternative = alternative.loc[alternative.strategy.ne("buy_and_hold")].reset_index(drop=True)
    central = central.rename(columns={"period": "target_period"})
    central.insert(0, "asset", INSTRUMENT)
    central["label_end_period"] = central.target_period
    central["has_signal"] = central.position.ne(0)
    central["cash_capital_end"] = float(parameters["initial_capital"]) * (1 + central.rf_return)
    central["excess_return"] = central.net_return - central.rf_return
    central["label"] = central.excess_return.gt(LABEL_TOLERANCE).astype("Int8").where(central.has_signal)
    central["label_status"] = central.has_signal.map({True: "labelled", False: "no_trade_signal"})
    central["capital_end_no_transaction_cost"] = alternative.capital_end
    central["net_return_no_transaction_cost"] = alternative.net_return
    central["excess_return_no_transaction_cost"] = alternative.net_return - alternative.rf_return
    central["label_no_transaction_cost"] = central.excess_return_no_transaction_cost.gt(
        LABEL_TOLERANCE).astype("Int8").where(central.has_signal)
    central["label_changed"] = central.label.ne(central.label_no_transaction_cost).astype("boolean")
    return central


def summarize_labels(dataset: pd.DataFrame) -> list[dict]:
    """Mostrar denominadores por regla, incluyendo el calendario y la muestra común."""
    summaries = []
    for strategy, rows in dataset.groupby("strategy", sort=False):
        active = rows.loc[rows.has_signal]
        ready = rows.loc[rows.training_ready]
        changed = int(ready.label_changed.sum())
        summaries.append({
            "strategy": strategy, "calendar_months": len(rows),
            "signals": len(active), "no_trade_months": int((~rows.has_signal).sum()),
            "positive_labels": int(active.label.eq(1).sum()),
            "negative_labels": int(active.label.eq(0).sum()),
            "complete_feature_months": int(rows.features_ready.sum()),
            "training_examples": len(ready),
            "training_positive": int(ready.label.eq(1).sum()),
            "training_negative": int(ready.label.eq(0).sum()),
            "changed_labels_all_signals": int(active.label_changed.sum()),
            "changed_labels_training": changed,
            "changed_fraction_training": changed / len(ready) if len(ready) else None,
        })
    return summaries
