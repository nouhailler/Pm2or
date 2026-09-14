from __future__ import annotations

import difflib
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pm2 import __version__
from pm2.application.context import ApplicationContext
from pm2.application.services import ProjectMethodologyError, ProjectService
from pm2.application.validation import ValidationService
from pm2.config import AppPaths
from pm2.infrastructure.archive import ArchiveError, ProjectArchiveService
from pm2.infrastructure.orm import ProjectModel
from pm2.methodology.models import PM2Configuration
from pm2.ui.crud import EntityCatalogPage
from pm2.ui.dialogs import ProjectDialog
from pm2.ui.pages import (
    CoreDataPage,
    DashboardPage,
    DocumentsPage,
    GatesPage,
    GovernancePage,
    LifecyclePage,
    Page,
    ProjectPage,
    RegistersPage,
    TraceabilityPage,
    ValidationPage,
    WelcomePage,
    WorkPlanPage,
)
from pm2.ui.wizards import PhaseAssistantPage

STYLE = """
QMainWindow, QWidget { background: #f4f6f9; color: #172033; font-size: 13px; }
QMenuBar, QMenu, QStatusBar { background: white; }
#sidebar { background: #18324a; border: none; color: #e9f1f8; outline: none; padding: 8px; }
#sidebar::item { min-height: 35px; border-radius: 5px; padding-left: 10px; }
#sidebar::item:selected { background: #2f6b91; color: white; }
#sidebar::item:hover { background: #254e70; }
#contextPanel { background: white; border-left: 1px solid #dce2e8; }
#appBrand { color: #18324a; font-weight: 700; font-size: 17px; padding: 10px; background: white; }
#pageTitle { font-size: 25px; font-weight: 700; color: #18324a; }
#pageSubtitle, #welcomeSubtitle { color: #667788; }
#welcomeTitle { font-size: 38px; font-weight: 700; color: #18324a; }
#sectionTitle { font-size: 17px; font-weight: 600; color: #254e70; }
#metricCard { background: white; border: 1px solid #dbe2e8; border-radius: 7px; min-width: 125px; }
#metricTitle { color: #667788; font-size: 12px; }
#metricValue { color: #18324a; font-size: 20px; font-weight: 700; }
#validationBadge { background: #e8eef8; color: #254e70; border-radius: 12px; padding: 7px 12px; }
QPushButton { background: white; border: 1px solid #b9c3cd; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover { background: #edf3f7; }
QPushButton#primaryButton { background: #255f85; color: white; border-color: #255f85; font-weight: 600; }
QPushButton#primaryButton:hover { background: #1d4d6d; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit { background: white; border: 1px solid #b9c3cd; border-radius: 4px; padding: 5px; }
QTableWidget, QTreeWidget, QTabWidget::pane { background: white; border: 1px solid #dbe2e8; }
QHeaderView::section { background: #e8eef8; color: #254e70; padding: 7px; border: none; border-right: 1px solid #d1d9e0; font-weight: 600; }
QGroupBox { background: white; border: 1px solid #dbe2e8; border-radius: 6px; margin-top: 10px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, context: ApplicationContext, paths: AppPaths) -> None:
        super().__init__()
        self.context = context
        self.paths = paths
        self.session: Session = context.database.session_factory()
        self.project: ProjectModel | None = None
        self.project_methodology: PM2Configuration | None = None
        self._methodology_cache: dict[tuple[str, str], PM2Configuration] = {}
        self.pages: list[Page] = []
        self.setWindowTitle("PM² Desktop")
        self.resize(1440, 900)
        self.setMinimumSize(1050, 680)
        self.setStyleSheet(STYLE)
        self._build_menu()
        self._build_shell()
        projects = self._project_service().list()
        if projects:
            try:
                self.activate_project(projects[0])
            except ProjectMethodologyError as exc:
                QMessageBox.critical(self, "Méthodologie invalide", str(exc))
                self.show_welcome()
        else:
            self.show_welcome()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&Fichier")
        new_action = QAction("Nouveau projet…", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_project)
        open_action = QAction("Ouvrir un projet…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_project)
        export_action = QAction("Exporter l’archive .pm2…", self)
        export_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        export_action.triggered.connect(self.export_archive)
        quit_action = QAction("Quitter", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addActions([new_action, open_action, export_action])
        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu("Projets récents")
        self._reload_recents()
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        project_menu = self.menuBar().addMenu("&Projet")
        validate_action = QAction("Valider la cohérence", self)
        validate_action.triggered.connect(lambda: self.navigate_to("Validation"))
        close_action = QAction("Fermer administrativement", self)
        close_action.triggered.connect(self.close_project)
        methodology_action = QAction("Méthodologie du projet…", self)
        methodology_action.triggered.connect(self.review_project_methodology)
        project_menu.addActions([validate_action, methodology_action, close_action])

        view_menu = self.menuBar().addMenu("&Affichage")
        refresh_action = QAction("Actualiser", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self.refresh_all)
        context_action = QAction("Panneau contextuel", self, checkable=True, checked=True)
        context_action.toggled.connect(self.context_panel_visibility)
        view_menu.addActions([refresh_action, context_action])

        tools_menu = self.menuBar().addMenu("&Outils")
        tools_menu.addAction(validate_action)
        help_menu = self.menuBar().addMenu("&Aide")
        about_action = QAction("À propos", self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)

    def _build_shell(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        brand = QLabel(f"PM² Desktop  ·  v{__version__}")
        brand.setObjectName("appBrand")
        outer.addWidget(brand)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        self.navigation = QListWidget()
        self.navigation.setObjectName("sidebar")
        self.navigation.setFixedWidth(220)
        self.navigation.currentRowChanged.connect(self._navigation_changed)
        body.addWidget(self.navigation)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, stretch=1)
        self.context_panel = QFrame()
        self.context_panel.setObjectName("contextPanel")
        self.context_panel.setFixedWidth(250)
        context_layout = QVBoxLayout(self.context_panel)
        context_title = QLabel("Contexte")
        context_title.setObjectName("sectionTitle")
        self.context_project = QLabel("Aucun projet")
        self.context_project.setWordWrap(True)
        self.context_phase = QLabel()
        self.context_methodology = QLabel()
        self.context_methodology.setWordWrap(True)
        self.context_validation = QLabel()
        self.context_validation.setWordWrap(True)
        validate = QPushButton("Afficher les validations")
        validate.clicked.connect(lambda: self.navigate_to("Validation"))
        context_layout.addWidget(context_title)
        context_layout.addWidget(self.context_project)
        context_layout.addWidget(self.context_phase)
        context_layout.addWidget(self.context_methodology)
        context_layout.addWidget(self.context_validation)
        context_layout.addWidget(validate)
        context_layout.addStretch()
        body.addWidget(self.context_panel)
        outer.addLayout(body)
        self.setCentralWidget(central)
        self.status_project = QLabel("Aucun projet")
        self.status_phase = QLabel("Phase : —")
        self.status_validation = QLabel("Validation : —")
        self.statusBar().addWidget(self.status_project, 1)
        self.statusBar().addPermanentWidget(self.status_phase)
        self.statusBar().addPermanentWidget(self.status_validation)

    def show_welcome(self) -> None:
        self.project = None
        self.project_methodology = None
        self.navigation.hide()
        self.context_panel.hide()
        self._clear_pages()
        welcome = WelcomePage()
        welcome.new_requested.connect(self.new_project)
        welcome.open_requested.connect(self.open_project)
        self.stack.addWidget(welcome)
        self.pages = [welcome]
        self.stack.setCurrentWidget(welcome)
        self._update_status()

    def activate_project(self, project: ProjectModel) -> None:
        methodology = self._resolve_project_methodology(project)
        self.project = project
        self.project_methodology = methodology
        self.navigation.show()
        self.context_panel.show()
        self._clear_pages()
        output = self.paths.data_dir / "exports" / project.reference
        definitions: list[tuple[str, Page]] = [
            ("Dashboard", DashboardPage(self.session, project)),
            ("Projet", ProjectPage(self.session, project)),
            ("Gouvernance", GovernancePage(self.session, project, methodology)),
            (
                "Lancement",
                PhaseAssistantPage(self.session, project, methodology, "LAUNCH"),
            ),
            (
                "Planification",
                PhaseAssistantPage(self.session, project, methodology, "PLANNING"),
            ),
            ("Plan de travail", WorkPlanPage(self.session, project)),
            ("Données métier", CoreDataPage(self.session, project)),
            ("Catalogue", EntityCatalogPage(self.session, project.id)),
            (
                "Exécution",
                PhaseAssistantPage(self.session, project, methodology, "EXECUTION"),
            ),
            (
                "Suivi & Contrôle",
                LifecyclePage(
                    "Suivi & Contrôle",
                    [
                        "Performance",
                        "Échéancier",
                        "Coûts",
                        "Besoins",
                        "Qualité",
                        "Acceptation",
                        "Transition",
                        "Mise en œuvre",
                    ],
                    "Le suivi transversal consolide les données du Work Plan et des registres.",
                ),
            ),
            ("Gates", GatesPage(self.session, project, methodology)),
            (
                "Clôture",
                PhaseAssistantPage(self.session, project, methodology, "CLOSING"),
            ),
            ("Registres", RegistersPage(self.session, project)),
            ("Traçabilité", TraceabilityPage(self.session, project)),
            (
                "Documents",
                DocumentsPage(self.session, self.context.database, project, methodology, output),
            ),
            ("Validation", ValidationPage(self.session, project)),
            (
                "Paramètres",
                LifecyclePage(
                    "Paramètres",
                    ["Projet", "Méthodologie", "Stockage", "Exports"],
                    f"{methodology.methodology.name} v{methodology.methodology.version} "
                    f"({methodology.methodology.language}), fonctionnement local sans dépendance serveur.",
                ),
            ),
        ]
        self.navigation.clear()
        self.pages = []
        for name, page in definitions:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.navigation.addItem(item)
            self.stack.addWidget(page)
            page.changed.connect(self.refresh_all)
            if isinstance(page, TraceabilityPage):
                page.navigate_requested.connect(self.navigate_to)
            if isinstance(page, PhaseAssistantPage):
                page.navigate_requested.connect(self.navigate_to)
            self.pages.append(page)
        self.navigation.setCurrentRow(0)
        self._update_recent(str(self.context.database.path or ""))
        self._update_status()

    def _clear_pages(self) -> None:
        self.pages.clear()
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()

    def _navigation_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            page = self.stack.currentWidget()
            if isinstance(page, Page):
                page.reload()

    def navigate_to(self, name: str) -> None:
        for index in range(self.navigation.count()):
            if self.navigation.item(index).data(Qt.ItemDataRole.UserRole) == name:
                self.navigation.setCurrentRow(index)
                return

    def new_project(self) -> None:
        dialog = ProjectDialog(self)
        if hasattr(dialog, "methodology"):
            identity = self.context.methodology.methodology
            dialog.methodology.setText(f"{identity.name} v{identity.version} — {identity.language}")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            project = self._project_service().create(**dialog.values())
            self.session.commit()
            self.activate_project(project)
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Création impossible", str(exc))

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un projet",
            str(self.paths.data_dir),
            "Projet PM² (*.pm2);;Base PM² (*.db)",
        )
        if not path:
            return
        source = Path(path)
        destination = source
        try:
            if source.suffix.lower() == ".pm2":
                projects_dir = self.paths.data_dir / "projects"
                destination = projects_dir / f"{source.stem}.db"
                if destination.exists():
                    answer = QMessageBox.question(
                        self,
                        "Projet existant",
                        "Une copie locale existe. La remplacer avec l’archive ?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        return
                ProjectArchiveService.open(source, destination, overwrite=True)
            self._switch_database(destination)
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))

    def _switch_database(self, path: Path) -> None:
        self.session.close()
        self.context.database.dispose()
        self.context = ApplicationContext.open(path, create=False)
        self.session = self.context.database.session_factory()
        projects = self._project_service().list()
        if not projects:
            raise ArchiveError("Aucun projet trouvé dans la base sélectionnée.")
        self.activate_project(projects[0])
        self._update_recent(str(path))

    def export_archive(self) -> None:
        if not self.project:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le projet",
            str(self.paths.data_dir / f"{self.project.reference}.pm2"),
            "Projet PM² (*.pm2)",
        )
        if not path:
            return
        try:
            output = ProjectArchiveService(self.context.database, self.session).save(
                self.project.id, Path(path)
            )
            QMessageBox.information(self, "Projet exporté", f"Archive créée :\n{output}")
        except Exception as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))

    def close_project(self) -> None:
        if not self.project:
            return
        try:
            methodology = self.project_methodology or self._resolve_project_methodology(
                self.project
            )
            project = ProjectService(self.session, methodology).close(self.project.id)
            self.session.commit()
            self.activate_project(project)
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Fermeture refusée", str(exc))

    def refresh_all(self) -> None:
        for page in self.pages:
            page.reload()
        self._update_status()

    def _update_status(self) -> None:
        if not self.project:
            self.status_project.setText("Aucun projet")
            self.status_phase.setText("Phase : —")
            self.status_validation.setText("Validation : —")
            self.context_methodology.setText("")
            return
        self.session.refresh(self.project)
        problems = ValidationService(self.session).validate_project(self.project.id)
        errors = sum(problem.severity == "ERROR" for problem in problems)
        warnings = sum(problem.severity == "WARNING" for problem in problems)
        self.status_project.setText(f"{self.project.reference} — {self.project.name}")
        self.status_phase.setText(f"Phase : {self.project.current_phase}")
        self.status_validation.setText(f"Validation : {errors} E / {warnings} A")
        self.context_project.setText(f"{self.project.reference}\n{self.project.name}")
        self.context_phase.setText(f"Phase actuelle\n{self.project.current_phase}")
        self.context_methodology.setText(
            f"Méthodologie figée\n{self.project.methodology_id.upper()} "
            f"{self.project.methodology_version}\nSHA-256 {self.project.methodology_hash[:12]}…"
        )
        self.context_validation.setText(
            f"Cohérence PM²\n{errors} erreur(s)\n{warnings} avertissement(s)"
        )

    def context_panel_visibility(self, visible: bool) -> None:
        self.context_panel.setVisible(visible and self.project is not None)

    def _project_service(self) -> ProjectService:
        return ProjectService(
            self.session,
            self.context.methodology,
            methodology_snapshot=self.context.methodology_snapshot,
            methodology_hash=self.context.methodology_hash,
        )

    def _resolve_project_methodology(self, project: ProjectModel) -> PM2Configuration:
        service = self._project_service()
        was_legacy = not project.methodology_snapshot or not project.methodology_hash
        project_configuration = service.methodology_for(project)
        if was_legacy:
            self.session.commit()
        if service.uses_current_methodology(project):
            return project_configuration
        cache_key = (project.id, project.methodology_hash)
        if cache_key in self._methodology_cache:
            return self._methodology_cache[cache_key]
        while True:
            choice = QMessageBox(self)
            choice.setIcon(QMessageBox.Icon.Warning)
            choice.setWindowTitle("Méthodologie différente")
            choice.setText(
                f"Projet créé avec {project_configuration.methodology.name} "
                f"{project.methodology_version}.\n"
                f"Méthodologie actuelle : "
                f"{self.context.methodology.methodology.name} "
                f"{self.context.methodology.methodology.version}."
            )
            choice.setInformativeText(
                "La méthodologie du projet n’est plus la version actuelle. "
                "Le projet continuera à utiliser son snapshot tant qu’une mise à niveau "
                "explicite n’est pas demandée."
            )
            keep_button = choice.addButton(
                f"Conserver {project.methodology_version}",
                QMessageBox.ButtonRole.AcceptRole,
            )
            compare_button = choice.addButton(
                "Examiner les différences", QMessageBox.ButtonRole.ActionRole
            )
            upgrade_button = choice.addButton(
                "Mettre à niveau", QMessageBox.ButtonRole.DestructiveRole
            )
            choice.setDefaultButton(keep_button)
            choice.exec()
            clicked = choice.clickedButton()
            if clicked is compare_button:
                self._show_methodology_diff(project)
                continue
            if clicked is upgrade_button:
                upgraded = service.upgrade_methodology(project)
                self.session.commit()
                self._methodology_cache[(project.id, project.methodology_hash)] = upgraded
                QMessageBox.information(
                    self,
                    "Méthodologie mise à niveau",
                    f"Le projet utilise désormais {project.methodology_id.upper()} "
                    f"{project.methodology_version}. L’opération a été auditée.",
                )
                return upgraded
            self._methodology_cache[cache_key] = project_configuration
            return project_configuration

    def _show_methodology_diff(self, project: ProjectModel) -> None:
        lines = difflib.unified_diff(
            project.methodology_snapshot.splitlines(),
            self.context.methodology_snapshot.splitlines(),
            fromfile=f"Projet — {project.methodology_version}",
            tofile=f"Actuelle — {self.context.methodology.methodology.version}",
            lineterm="",
        )
        dialog = QDialog(self)
        dialog.setWindowTitle("Différences méthodologiques")
        dialog.resize(1050, 720)
        layout = QVBoxLayout(dialog)
        explanation = QLabel(
            "Comparaison du snapshot immuable du projet avec la méthodologie installée."
        )
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText("\n".join(lines) or "Aucune différence textuelle.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fermer")
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(explanation)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        dialog.exec()

    def review_project_methodology(self) -> None:
        if self.project is None:
            return
        service = self._project_service()
        if service.uses_current_methodology(self.project):
            QMessageBox.information(
                self,
                "Méthodologie du projet",
                f"Le projet utilise la méthodologie actuelle "
                f"{self.project.methodology_id.upper()} {self.project.methodology_version}.\n"
                f"SHA-256 : {self.project.methodology_hash}",
            )
            return
        self._methodology_cache.clear()
        self.activate_project(self.project)

    def _recent_paths(self) -> list[str]:
        try:
            raw = json.loads(self.paths.recent_file.read_text(encoding="utf-8"))
            return [str(path) for path in raw if Path(path).exists()][:8]
        except (OSError, json.JSONDecodeError, TypeError):
            return []

    def _update_recent(self, path: str) -> None:
        if not path:
            return
        recent = [path, *(item for item in self._recent_paths() if item != path)][:8]
        self.paths.recent_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.recent_file.write_text(
            json.dumps(recent, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._reload_recents()

    def _reload_recents(self) -> None:
        self.recent_menu.clear()
        recent = self._recent_paths()
        if not recent:
            action = self.recent_menu.addAction("Aucun projet récent")
            action.setEnabled(False)
            return
        for path in recent:
            action = self.recent_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda _checked=False, value=path: self._open_recent(value))

    def _open_recent(self, path: str) -> None:
        try:
            self._switch_database(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))

    def about(self) -> None:
        QMessageBox.about(
            self,
            "À propos de PM² Desktop",
            f"<b>PM² Desktop {__version__}</b><br>Gestion de projets PM² v3.1 en français.<br>"
            "Application locale et hors ligne — PySide6, SQLite et SQLAlchemy.",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        try:
            self.session.commit()
            self.session.close()
            self.context.database.dispose()
        finally:
            event.accept()
