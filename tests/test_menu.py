from pathlib import Path

from tfm import cli, menu


def test_menu_selects_snapshot_and_delegates(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config = config_dir / "data.toml"
    config.write_text((Path(__file__).parents[1] / "configs/data.toml").read_text())
    raw = tmp_path / "data/raw/yahoo/SPY/example"
    raw.mkdir(parents=True)
    (raw / "manifest.json").write_text('{"instrument":"SPY","snapshot_id":"example","parameters":{"start":"1993-01-29","end":"2021-01-01"}}')
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text('{"prepared_dir":"prepared"}')
    answers = iter(["invalid", "2", str(config), "999", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    calls = []
    def prepare(config_path, snapshot):
        calls.append((config_path, snapshot))
        return run
    monkeypatch.setattr(menu, "run_prepare_prices", prepare)
    assert menu.interactive_menu() == 0
    assert calls == [(config, raw)]


def test_no_arguments_use_menu_only_in_terminal(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main([]) == 0
    assert "prepare-prices" in capsys.readouterr().out
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    calls = []
    monkeypatch.setattr(cli, "interactive_menu", lambda: calls.append(True) or 0)
    assert cli.main([]) == 0
    assert calls == [True]
