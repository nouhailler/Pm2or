#!/usr/bin/env python3
"""Capture de vrais écrans de PM² Desktop, sur une base éphémère et un projet fictif.

À lancer depuis la racine du dépôt, avec l'environnement de l'application :

    QT_QPA_PLATFORM=offscreen PM2_DISABLE_UPDATE_CHECK=1 PYTHONPATH=src \
        .venv/bin/python landing/scripts/capture_screens.py --output build/landing-captures

Le script ne modifie ni l'application ni la base locale de l'utilisateur.
"""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QScrollArea, QTabWidget

from pm2.application.context import ApplicationContext
from pm2.application.system_settings import SystemSettingsStore
from pm2.config import AppPaths
from pm2.ui.main_window import MainWindow
from pm2.ui.project_workflow import ProjectWorkflow

REPOSITORY = Path(__file__).resolve().parents[2]

# (fichier, page de l'application, libellé de l'onglet à ouvrir ou None)
SCREENS = (
    ("cockpit", "Dashboard", None),
    ("parcours", "Dashboard", None),
    ("lancement", "Lancement", None),
    ("plan-de-travail", "Plan de travail", None),
    ("registres", "Registres", None),
    ("objets-orphelins", "Traçabilité", "Objets orphelins"),
    ("conformite", "Validation", None),
    ("audit-trail", "Audit Trail", None),
    ("documents", "Documents", None),
    ("glossaire", "Glossaire", None),
)


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "create_training_project", REPOSITORY / "scripts" / "create_training_project.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Générateur du projet d'entraînement introuvable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_tab(page, label: str) -> None:
    for tabs in page.findChildren(QTabWidget):
        for index in range(tabs.count()):
            if label.casefold() in tabs.tabText(index).casefold():
                tabs.setCurrentIndex(index)
                return


def show_workflow(page, app) -> None:
    workflow = page.findChild(ProjectWorkflow)
    if workflow is None:
        raise RuntimeError("Parcours PM² introuvable sur le tableau de bord.")
    app.processEvents()
    area = next(
        candidate for candidate in page.findChildren(QScrollArea)
        if candidate.isAncestorOf(workflow)
    )
    area.ensureWidgetVisible(workflow, 0, 12)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pm2-captures-") as temporary:
        root = Path(temporary)
        database = root / "project.db"
        context = ApplicationContext.open(database)
        load_generator().create_project(context)
        app = QApplication.instance() or QApplication([])
        paths = AppPaths(root, database, root / "captures.log", root / "recent.json")
        settings = SystemSettingsStore(root / "system-settings.json")
        settings.value.legal_accepted_version = "1"
        settings.value.automatic_update_checks = False
        settings.save()
        window = MainWindow(context, paths)
        window.resize(1500, 950)
        window.show()
        app.processEvents()
        for filename, page_name, tab in SCREENS:
            window.navigate_to(page_name)
            page = window.stack.currentWidget()
            if tab:
                select_tab(page, tab)
            if filename == "parcours":
                show_workflow(page, app)
            for _ in range(5):
                app.processEvents()
            target = output / f"{filename}.png"
            if not window.grab().save(str(target), "PNG"):
                raise RuntimeError(f"Capture impossible : {target}")
            print(target)
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
