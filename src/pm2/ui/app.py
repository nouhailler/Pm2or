from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from pm2 import __version__
from pm2.application.context import ApplicationContext
from pm2.config import AppPaths
from pm2.ui.main_window import MainWindow


def run_gui(database_path: Path | None = None) -> int:
    paths = AppPaths.default()
    paths.ensure()
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("PM² Desktop")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("PM² Desktop")
    QLocale.setDefault(QLocale(QLocale.Language.French, QLocale.Country.France))
    translator = QTranslator(application)
    qt_translation = Path(__import__("PySide6").__file__).parent / "translations" / "qtbase_fr.qm"
    if translator.load(str(qt_translation)):
        application.installTranslator(translator)
    context = ApplicationContext.open(database_path or paths.database)
    window = MainWindow(context, paths)
    window.show()
    return application.exec()
