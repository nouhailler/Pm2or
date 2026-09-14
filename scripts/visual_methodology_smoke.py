"""Capture le choix de méthodologie et la comparaison sur un projet historique."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from pm2.application.context import ApplicationContext
from pm2.application.services import ProjectService
from pm2.config import AppPaths
from pm2.methodology import bundle_methodology
from pm2.ui.main_window import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build/visual-methodology-qa"))
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    database = output / f"qa-{uuid4().hex}.db"
    context = ApplicationContext.open(database)
    with context.database.session() as session:
        ProjectService(session, context.methodology).create(
            reference="HIST-2026", name="Projet historique PM² 3.1"
        )
    future = context.methodology.model_copy(
        update={
            "methodology": context.methodology.methodology.model_copy(update={"version": "3.2"})
        }
    )
    context.methodology_bundle = bundle_methodology(future)

    def keep() -> None:
        message = application.activeModalWidget()
        assert isinstance(message, QMessageBox)
        next(
            button for button in message.buttons() if button.text().startswith("Conserver")
        ).click()

    def capture_diff() -> None:
        dialog = application.activeModalWidget()
        assert isinstance(dialog, QDialog)
        assert dialog.grab().save(str(output / "02-differences.png"))
        QTimer.singleShot(0, keep)
        dialog.reject()

    def capture_warning() -> None:
        message = application.activeModalWidget()
        assert isinstance(message, QMessageBox)
        assert message.grab().save(str(output / "01-avertissement.png"))
        QTimer.singleShot(0, capture_diff)
        next(button for button in message.buttons() if button.text().startswith("Examiner")).click()

    QTimer.singleShot(0, capture_warning)
    paths = AppPaths(output, database, output / "app.log", output / "recent.json")
    window = MainWindow(context, paths)
    window.show()
    application.processEvents()
    assert window.project_methodology is not None
    assert window.project_methodology.methodology.version == "3.1"
    assert window.grab().save(str(output / "03-projet-conserve.png"))
    window.close()
    print(json.dumps({"status": "ok", "project_version": "3.1", "current_version": "3.2"}))


if __name__ == "__main__":
    main()
