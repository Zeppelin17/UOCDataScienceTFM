from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest

from tfm import cli, menu
from tfm.backtesting.buy_and_hold import simulate_buy_and_hold
from tfm.backtesting.engine import simulate_long_cash
from tfm.evaluation.simulation import summarize_simulation
from tfm.preparation.prices import prepare_prices
from tfm.sources import prices as source


@pytest.mark.parametrize("cost_bps, final", [(0, 1.1), (5, 1.09945)])
def test_entry_delay_and_costs_match_hand_calculation(cost_bps, final):
    prices = pd.DataFrame({
        "asset": ["SPY"] * 3,
        "observed_at": pd.to_datetime(["2020-12-28", "2020-12-29", "2020-12-30"]),
        "adjusted_close": [100.0, 110.0, 121.0],
        "dividends": [0.0, 0.0, 1.0],  # No se suma al retorno ajustado.
    })
    equity = simulate_buy_and_hold(prices, cost_bps=cost_bps)
    assert equity["position_before"].tolist() == [0, 0, 1]
    assert equity["position_after"].tolist() == [0, 1, 1]
    assert equity["turnover"].tolist() == [0, 1, 0]
    assert equity["net_capital"].iloc[-1] == pytest.approx(final)
    summary = summarize_simulation(equity)
    assert summary["gross_total_return"] == pytest.approx(0.1)
    assert summary["total_cost_amount"] == pytest.approx(cost_bps / 10000)
    assert summary["max_drawdown"] == pytest.approx(cost_bps / 10000)


def test_common_engine_applies_return_before_exit_and_preserves_cash():
    prices = pd.DataFrame({
        "asset": ["SPY"] * 4, "observed_at": pd.date_range("2020-12-28", periods=4),
        "adjusted_close": [100.0, 110.0, 99.0, 198.0],
    })
    equity = simulate_long_cash(prices, pd.Series([0, 1, 0, 0]), cost_bps=5)
    # Entrada al segundo cierre; caída 10 % hasta la salida; después efectivo.
    expected = (1 - 0.0005) * 0.9 * (1 - 0.0005)
    assert equity["net_capital"].iloc[-1] == pytest.approx(expected)
    assert equity["gross_capital"].iloc[-1] == pytest.approx(0.9)
    assert equity["turnover"].sum() == 2


def make_project(tmp_path, *, holdout=False):
    root = Path(__file__).parents[1]
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    for name in ("data.toml", "experiment_base.toml", "buy_and_hold.toml"):
        text = (root / "configs" / name).read_text()
        if name == "buy_and_hold.toml":
            text = text.replace('start = "1993-01-29"', 'start = "2020-12-28"')
            text = text.replace('end = "2020-12-31"', 'end = "2020-12-30"')
        (config_dir / name).write_text(text)
    raw = tmp_path / "raw"
    raw.mkdir()
    dates = ["2020-12-24", "2020-12-28", "2020-12-29", "2021-01-04" if holdout else "2020-12-30"]
    frame = pd.DataFrame({
        "Open": [90.0, 100.0, 110.0, 121.0], "High": [90.0, 100.0, 110.0, 121.0],
        "Low": [90.0, 100.0, 110.0, 121.0], "Close": [90.0, 100.0, 110.0, 121.0],
        "Adj Close": [90.0, 100.0, 110.0, 121.0], "Volume": [1000] * 4,
        "Dividends": [0.0] * 4, "Stock Splits": [0.0] * 4,
    }, index=pd.to_datetime(dates))
    frame.to_parquet(raw / "prices.parquet")
    (raw / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "provider": "yahoo", "instrument": "SPY",
        "snapshot_id": "test", "data_file": "prices.parquet", "rows": 4,
        "sha256": sha256((raw / "prices.parquet").read_bytes()).hexdigest(),
        "parameters": {"start": "2020-12-24", "end": "2021-01-05"},
    }))
    prepared = prepare_prices(raw, tmp_path / "data/processed")
    return config_dir / "buy_and_hold.toml", prepared


@pytest.mark.parametrize("bad", ["tampered", "holdout", "cost", "interval"])
def test_invalid_simulation_records_failure_without_publishing(tmp_path, bad, capsys):
    config, prepared = make_project(tmp_path, holdout=bad == "holdout")
    if bad == "tampered":
        with (prepared / "prices.parquet").open("ab") as handle:
            handle.write(b"changed")
    elif bad == "cost":
        config.write_text(config.read_text().replace("cost_bps = 5.0", "cost_bps = nan"))
    elif bad == "interval":
        config.write_text(config.read_text().replace('end = "2020-12-30"', 'end = "2021-01-04"'))
    assert cli.main(["simulate-buy-and-hold", "--config", str(config), "--prepared", str(prepared)]) == 1
    run = next((tmp_path / "outputs/runs").iterdir())
    record = json.loads((run / "run.json").read_text())
    assert record["status"] == "failed"
    assert not (run / "equity.parquet").exists()
    assert not (run / "summary.json").exists()
    assert "Registro:" in capsys.readouterr().err


def test_offline_cli_replay_and_menu_use_same_flow(tmp_path, monkeypatch, capsys):
    config, prepared = make_project(tmp_path)
    original_hash = sha256((prepared / "prices.parquet").read_bytes()).hexdigest()
    def no_download(**kwargs):
        pytest.fail("Una simulación no debe descargar datos")
    monkeypatch.setattr(source.yf, "download", no_download)
    args = ["simulate-buy-and-hold", "--config", str(config), "--prepared", str(prepared)]
    assert cli.main(args) == 0
    first = next((tmp_path / "outputs/runs").iterdir())
    summary = json.loads((first / "summary.json").read_text())
    assert summary["first_session"] == "2020-12-28"  # Respeta el intervalo, no toda la preparación.
    assert summary["entry_at"] == "2020-12-29"
    assert summary["final_net_capital"] == pytest.approx(1.09945)
    assert (first / "config.toml").read_bytes() == config.read_bytes()
    assert (first / "validation_policy.toml").read_bytes() == (tmp_path / "configs/experiment_base.toml").read_bytes()
    assert cli.main(args) == 0
    runs = list((tmp_path / "outputs/runs").iterdir())
    second = next(path for path in runs if path != first)
    pd.testing.assert_frame_equal(pd.read_parquet(first / "equity.parquet"), pd.read_parquet(second / "equity.parquet"))
    monkeypatch.chdir(tmp_path)
    answers = iter(["6", "99", "1", "", "3", "", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert menu.interactive_menu() == 0
    assert len(list((tmp_path / "outputs/runs").iterdir())) == 3
    assert sha256((prepared / "prices.parquet").read_bytes()).hexdigest() == original_hash
    output = capsys.readouterr().out
    assert "Rotación acumulada: 1.00" in output
    assert "Configuración independiente de simulación:" in output
    assert "simulate-buy-and-hold | completed" in output
