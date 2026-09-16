from pathlib import Path

import pytest

from pm2.application.context import ApplicationContext
from pm2.application.services import ProjectService
from pm2.config import AppPaths
from pm2.infrastructure.archive import ArchiveError
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


def test_failed_database_switch_keeps_current_project(qtbot, tmp_path: Path) -> None:
    current = ApplicationContext.open(tmp_path / "current.db")
    with current.database.session() as session:
        project = ProjectService(session, current.methodology).create(
            reference="CURRENT", name="Projet courant"
        )
        project_id = project.id
    paths = AppPaths(
        tmp_path / "data",
        tmp_path / "current.db",
        tmp_path / "pm2.log",
        tmp_path / "recent.json",
    )
    paths.ensure()
    window = MainWindow(current, paths)
    qtbot.addWidget(window)
    empty = ApplicationContext.open(tmp_path / "empty.db")
    empty.database.dispose()

    with pytest.raises(ArchiveError, match="Aucun projet"):
        window._switch_database(tmp_path / "empty.db")

    assert window.context is current
    assert window.project is not None
    assert window.project.id == project_id
    assert window.session.get(type(window.project), project_id) is not None
    window.close()
