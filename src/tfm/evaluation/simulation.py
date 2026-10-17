"""Resumen descriptivo del primer simulador; no evalúa capacidad predictiva."""

import pandas as pd


def summarize_simulation(equity: pd.DataFrame) -> dict:
    changes = equity["turnover"].gt(0)
    return {
        "sessions": len(equity),
        "first_session": equity["observed_at"].iloc[0].date().isoformat(),
        "last_session": equity["observed_at"].iloc[-1].date().isoformat(),
        "decision_at": equity["observed_at"].iloc[0].date().isoformat(),
        "entry_at": equity.loc[changes, "observed_at"].iloc[0].date().isoformat() if changes.any() else None,
        "initial_capital": 1.0,
        "final_gross_capital": float(equity["gross_capital"].iloc[-1]),
        "final_net_capital": float(equity["net_capital"].iloc[-1]),
        "gross_total_return": float(equity["gross_capital"].iloc[-1] - 1),
        "net_total_return": float(equity["net_capital"].iloc[-1] - 1),
        "total_cost_amount": float(equity["cost_amount"].sum()),
        "total_turnover": float(equity["turnover"].sum()),
        "max_drawdown": float(-equity["drawdown"].min()),
    }
