"""Consulta y navegación de registros sin ejecutar flujos ni alterar datos."""

import json
from pathlib import Path

from tfm import menu, run_browser


def test_history_pagination_filter_selection_and_read_only(tmp_path, monkeypatch, capsys):
    config = tmp_path / "configs/data.toml"
    prepared = tmp_path / "data/processed/shiller_monthly/example"
    prepared.mkdir(parents=True)
    table = prepared / "monthly.parquet"
    table.write_bytes(b"Existing table; browser does not read or rewrite it")
    for i in range(12):
        directory = tmp_path / "outputs/runs" / f"20261018T1200{i:02d}Z_example{i:02d}"
        directory.mkdir(parents=True)
        record = {"run_id": directory.name, "command": "prepare-shiller" if i < 10 else "simulate-buy-and-hold",
                  "status": "completed", "started_at_utc": f"2026-10-18T12:00:{i:02d}+00:00",
                  "prepared_dir": str(prepared)}
        (directory / "run.json").write_text(json.dumps(record))
        (directory / "quality_report.json").write_text(json.dumps(
            {"rows": 768, "first_period": "1926-01", "last_period": "1989-12", "status": "passed"}))
    broken = tmp_path / "outputs/runs/broken/run.json"
    broken.parent.mkdir()
    broken.write_text("Invalid JSON")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    answers = iter(["n", "1", "1", "", "0", "t", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    opened = []
    monkeypatch.setattr(run_browser, "_reveal", lambda path: opened.append(path))
    run_browser.browse_runs(config, lambda: None)
    assert opened == [table]
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    output = capsys.readouterr().out
    assert "Página 1 de 2 | 10 ejecuciones" in output
    assert "Página 2 de 2" in output
    assert "Todas las tareas" in output and "Comprar y mantener SPY" in output
    assert "Filas: 768" in output and "1926-01 → 1989-12" in output
    assert "example01" not in output and str(tmp_path) not in output
    assert "Registros ilegibles omitidos: 1" in output


def test_finder_uses_local_arguments_and_ignores_external_metadata(tmp_path, monkeypatch):
    root = tmp_path / "project"
    directory = root / "outputs/runs/example"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "monthly.parquet").write_bytes(b"external")
    link = root / "linked"
    link.symlink_to(outside, target_is_directory=True)
    record = {"command": "prepare-shiller", "prepared_dir": str(link), "snapshot_dir": str(outside)}
    actions = run_browser._actions(root, directory, record)
    assert actions == [("Abrir carpeta de esta ejecución en Finder", directory)]
    file = directory / "file with spaces;$(literal).json"
    file.write_text("{}")
    calls = []
    monkeypatch.setattr(run_browser.sys, "platform", "darwin")
    monkeypatch.setattr(run_browser.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    run_browser._reveal(file)
    run_browser._reveal(directory)
    assert calls[0][0] == ["open", "-R", str(file)]
    assert calls[1][0] == ["open", str(directory)]
    assert all(not kwargs.get("shell", False) for _, kwargs in calls)


def test_return_from_history_does_not_require_an_extra_pause(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prompts = []
    answers = iter(["3", "0", "0"])
    def answer(prompt):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr(menu, "_clear_screen", lambda: None)
    assert menu.interactive_menu() == 0
    assert not any("Pulsa Intro" in prompt for prompt in prompts)
