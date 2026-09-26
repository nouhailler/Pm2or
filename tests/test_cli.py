from __future__ import annotations

import json
from pathlib import Path

import pytest

from pm2 import __version__
from pm2.application.context import ApplicationContext
from pm2.application.diagnostics import export_diagnostics
from pm2.cli import main, parser


def test_parser_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        parser().parse_args(["--version"])
    assert __version__ in capsys.readouterr().out


def test_headless_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("PM2_DATA_DIR", str(tmp_path / "data"))
    assert main(["--headless-check"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["tables"] >= 48


def test_anonymized_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PM2_DATA_DIR", str(tmp_path / "private-profile"))
    destination = tmp_path / "support" / "diagnostic.json"
    assert main(["--diagnostics", str(destination)]) == 0
    response = json.loads(capsys.readouterr().out)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    serialized = destination.read_text(encoding="utf-8")
    assert response == {"status": "ok", "diagnostics": str(destination)}
    assert payload["database"]["schema_revision"] == "0004"
    assert payload["application"]["version"] == __version__
    assert "private-profile" not in serialized
    assert "database" not in payload["runtime"]


def test_diagnostic_write_failure_removes_temporary_file(
    context: ApplicationContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "support" / "diagnostic.json"

    def fail_dump(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("pm2.application.diagnostics.json.dump", fail_dump)
    with pytest.raises(OSError, match="disk full"):
        export_diagnostics(context, destination)
    assert not destination.exists()
    assert list(destination.parent.glob("*.tmp")) == []
