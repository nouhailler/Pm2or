from pathlib import Path

from pm2.application.context import ApplicationContext
from pm2.config import AppPaths
from pm2.ui.main_window import MainWindow


def test_main_window_smoke(qtbot, tmp_path: Path) -> None:
    context = ApplicationContext.open(tmp_path / "ui.db")
    paths = AppPaths(tmp_path, tmp_path / "ui.db", tmp_path / "app.log", tmp_path / "recent.json")
    window = MainWindow(context, paths)
    qtbot.addWidget(window)
    window.show()
    assert window.windowTitle() == "PM² Desktop"
    assert window.stack.count() == 1
    assert window.stack.currentWidget().objectName() == ""  # accueil affiché sans projet
