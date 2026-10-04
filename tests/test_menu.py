from pathlib import Path

from tfm import cli, menu


def test_menu_selects_snapshot_and_delegates(tmp_path, monkeypatch, capsys):
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
    (run / "quality_report.json").write_text('{"rows":2,"first_session":"2020-12-30","last_session":"2020-12-31","status":"passed"}')
    monkeypatch.chdir(tmp_path)
    answers = iter(["invalid", "", "2", "999", "1", "", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    calls = []
    def prepare(config_path, snapshot):
        calls.append((config_path, snapshot))
        return run
    monkeypatch.setattr(menu, "run_prepare_prices", prepare)
    assert menu.interactive_menu() == 0
    assert calls == [(Path("configs/data.toml"), raw)]
    output = capsys.readouterr().out
    assert "Sesiones: 2" in output
    assert "Controles de calidad: superados" in output
    assert "Periodo: 2020-12-30 → 2020-12-31" in output


def test_no_arguments_use_menu_only_in_terminal(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main([]) == 0
    assert "prepare-prices" in capsys.readouterr().out
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    calls = []
    monkeypatch.setattr(cli, "interactive_menu", lambda: calls.append(True) or 0)
    assert cli.main([]) == 0
    assert calls == [True]


def test_view_is_direct_and_configuration_changes_are_explicit(tmp_path, monkeypatch, capsys):
    directory = tmp_path / "configs"
    directory.mkdir()
    text = (Path(__file__).parents[1] / "configs/data.toml").read_text()
    (directory / "data.toml").write_text(text)
    (directory / "alternative.toml").write_text(text.replace("1993-01-29", "2000-01-01"))
    monkeypatch.chdir(tmp_path)
    answers = iter(["4", "", "5", "missing.toml", "", "4", "", "5", "configs/alternative.toml", "", "4", "", "0"])
    prompts = []
    monkeypatch.setattr(menu, "_clear_screen", lambda: print("[pantalla limpia]"))
    def answer(prompt):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr("builtins.input", answer)
    assert menu.interactive_menu() == 0
    assert sum("Ruta del archivo" in prompt for prompt in prompts) == 2
    output = capsys.readouterr().out
    assert sum("Pulsa Intro" in prompt for prompt in prompts) == 5
    assert output.count("[pantalla limpia]") >= 10
    assert "Error:" in output
    assert "Configuración cambiada para esta sesión" in output
    assert "Configuración en uso: configs/alternative.toml" in output
    assert "Periodo: 2000-01-01" in output
