from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pm2.ui import app


def test_gui_startup_wires_qt_and_main_window(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[Any] = []

    class FakeApplication:
        @classmethod
        def instance(cls) -> FakeApplication:
            return cls()

        def setApplicationName(self, value: str) -> None:
            calls.append(("name", value))

        def setApplicationVersion(self, value: str) -> None:
            calls.append(("version", value))

        def setOrganizationName(self, value: str) -> None:
            calls.append(("organization", value))

        def installTranslator(self, _translator: Any) -> None:
            calls.append("translator")

        def exec(self) -> int:
            return 7

    class FakeTranslator:
        def __init__(self, _parent: Any) -> None:
            pass

        def load(self, _path: str) -> bool:
            return False

    class FakeWindow:
        def __init__(self, context: Any, paths: Any) -> None:
            calls.append(("window", context, paths))

        def show(self) -> None:
            calls.append("show")

    paths = SimpleNamespace(database=tmp_path / "default.db", ensure=lambda: None)
    context = object()
    monkeypatch.setattr(app, "QApplication", FakeApplication)
    monkeypatch.setattr(app, "QTranslator", FakeTranslator)
    monkeypatch.setattr(app.AppPaths, "default", lambda: paths)
    monkeypatch.setattr(app.ApplicationContext, "open", lambda path: (calls.append(path), context)[1])
    monkeypatch.setattr(app, "MainWindow", FakeWindow)
    monkeypatch.setattr(app, "install_tooltip_support", lambda value: calls.append("tooltips"))
    monkeypatch.setattr(app, "install_row_detail_support", lambda value: calls.append("details"))

    selected = tmp_path / "selected.db"
    assert app.run_gui(selected) == 7
    assert selected in calls
    assert "tooltips" in calls and "details" in calls and "show" in calls
