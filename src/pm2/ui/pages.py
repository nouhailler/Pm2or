from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.artifacts import ARTIFACT_SCHEMAS
from pm2.application.crud import EntityCrudService
from pm2.application.documents import DocumentService
from pm2.application.export import ExportService
from pm2.application.services import (
    AcceptanceService,
    DeliverableService,
    GateService,
    GovernanceService,
    MeetingService,
    QualityService,
    RegisterService,
    RequirementService,
    ResponsibilityService,
    TraceabilityService,
    TransitionService,
    WorkflowService,
    WorkPlanService,
    project_counts,
)
from pm2.application.validation import ValidationService
from pm2.domain.enums import GateDecisionType
from pm2.infrastructure.database import Database
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceTestModel,
    ChangeModel,
    DecisionModel,
    DeliverableModel,
    DocumentModel,
    DocumentVersionModel,
    ImplementationActivityModel,
    IssueModel,
    MeetingModel,
    ProjectModel,
    ProjectRoleAssignmentModel,
    QualityControlModel,
    RequirementModel,
    ResponsibilityAssignmentModel,
    RiskModel,
    RoleModel,
    StakeholderModel,
    TaskDependencyModel,
    TaskModel,
    TraceLinkModel,
    TransitionActivityModel,
    WbsNodeModel,
)
from pm2.methodology.models import PM2Configuration
from pm2.ui.crud import FIELD_LABELS, EntityCatalogPage, EntityEditDialog
from pm2.ui.dialogs import RegisterItemDialog, TraceLinkDialog, WbsNodeDialog
from pm2.ui.project_workflow import ProjectWorkflow


class Page(QWidget):
    changed = Signal()

    def reload(self) -> None:
        pass


class WelcomePage(Page):
    new_requested = Signal()
    open_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("PM² Desktop")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Gestion de projets PM² v3.1 — locale et hors ligne")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("welcomeSubtitle")
        new_button = QPushButton("Créer un nouveau projet")
        new_button.setObjectName("primaryButton")
        new_button.setMinimumSize(300, 44)
        open_button = QPushButton("Ouvrir un projet .pm2")
        open_button.setMinimumSize(300, 42)
        new_button.clicked.connect(self.new_requested)
        open_button.clicked.connect(self.open_requested)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(32)
        layout.addWidget(new_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(30)
        layout.addWidget(
            QLabel("Les projets récents apparaissent dans le menu Fichier."),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        layout.addStretch()


class MetricCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        self.title = QLabel(title)
        self.title.setObjectName("metricTitle")
        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        layout.addWidget(self.title)
        layout.addWidget(self.value)


class DashboardPage(Page):
    navigate_requested = Signal(str)

    def __init__(self, session: Session, project: ProjectModel, methodology: PM2Configuration) -> None:
        super().__init__()
        self.session, self.project = session, project
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        self.dashboard_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Tableau de bord")
        title.setObjectName("pageTitle")
        self.project_label = QLabel()
        self.project_label.setObjectName("pageSubtitle")
        self.project_label.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(self.project_label)
        heading.addLayout(title_box, 1)
        heading.addStretch()
        self.validation_badge = QLabel()
        self.validation_badge.setWordWrap(True)
        self.validation_badge.setObjectName("validationBadge")
        heading.addWidget(self.validation_badge)
        root.addLayout(heading)
        self.workflow = ProjectWorkflow(session, project, methodology)
        self.workflow.navigate_requested.connect(self.navigate_requested)
        root.addWidget(self.workflow)
        scroll.viewport().installEventFilter(self)
        cards_layout = QGridLayout()
        titles = [
            ("phase", "Phase"),
            ("gate", "Prochain gate"),
            ("progress", "Avancement"),
            ("budget", "Budget"),
            ("risks", "Risques ouverts"),
            ("issues", "Problèmes ouverts"),
            ("changes", "Modifications"),
            ("deliverables", "Livrables"),
            ("requirements", "Exigences"),
            ("documents", "Documents"),
        ]
        self.cards: dict[str, MetricCard] = {}
        for index, (key, label) in enumerate(titles):
            card = MetricCard(label)
            self.cards[key] = card
            cards_layout.addWidget(card, index // 3, index % 3)
        root.addLayout(cards_layout)
        actions_group = QGroupBox("Actions requises")
        actions_layout = QVBoxLayout(actions_group)
        self.actions = QLabel()
        self.actions.setWordWrap(True)
        actions_layout.addWidget(self.actions)
        root.addWidget(actions_group)
        root.addStretch()
        self.reload()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.dashboard_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.workflow.layout_route(watched.width())
        return super().eventFilter(watched, event)

    def reload(self) -> None:
        self.session.refresh(self.project)
        counts = project_counts(self.session, self.project.id)
        phase_names = {phase.code: phase.name for phase in self.workflow.phases}
        gate_names = {gate.from_phase: gate.name for gate in self.workflow.methodology.gates}
        closed = self.project.status in {"CLOSED", "ARCHIVED"}
        values = {
            **counts,
            "phase": "Clos" if closed else phase_names.get(self.project.current_phase, self.project.current_phase),
            "gate": "—" if closed else gate_names.get(self.project.current_phase, "Fermeture"),
            "budget": f"{self.project.approved_budget:,.2f} {self.project.currency}",
            "progress": f"{counts['progress']} %",
        }
        for key, card in self.cards.items():
            card.value.setText(str(values[key]))
        self.project_label.setText(f"{self.project.reference} — {self.project.name}")
        self.workflow.reload()
        problems = ValidationService(self.session).validate_project(self.project.id)
        errors = sum(problem.severity == "ERROR" for problem in problems)
        warnings = sum(problem.severity == "WARNING" for problem in problems)
        self.validation_badge.setText(f"{errors} erreur(s) · {warnings} avertissement(s)")
        urgent = [problem for problem in problems if problem.severity in {"ERROR", "WARNING"}][:5]
        self.actions.setText(
            "\n".join(f"• [{p.severity}] {p.message}" for p in urgent) or "Aucune action requise."
        )


class ProjectPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        title = QLabel("Projet")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        overview = QWidget()
        form = QFormLayout(overview)
        self.fields: dict[str, QLineEdit | QPlainTextEdit] = {}
        for key, label in (
            ("reference", "Référence"),
            ("name", "Nom"),
            ("description", "Description"),
            ("project_manager", "Chef de Projet"),
            ("business_owner", "Porteur du Projet"),
            ("current_phase", "Phase"),
            ("status", "Statut"),
        ):
            widget: QLineEdit | QPlainTextEdit
            widget = QPlainTextEdit() if key == "description" else QLineEdit()
            widget.setReadOnly(True)
            if isinstance(widget, QPlainTextEdit):
                widget.setMaximumHeight(100)
            self.fields[key] = widget
            form.addRow(label, widget)
        tabs.addTab(overview, "Vue d’ensemble")
        for name in (
            "Objectifs",
            "Périmètre",
            "Contraintes",
            "Budget",
            "Jalons",
            "Relations / Traçabilité",
        ):
            tabs.addTab(
                InfoPanel(
                    name, "Les informations sont alimentées par les données structurées du projet."
                ),
                name,
            )
        self.reload()

    def reload(self) -> None:
        self.session.refresh(self.project)
        for key, widget in self.fields.items():
            value = str(getattr(self.project, key) or "")
            if isinstance(widget, QPlainTextEdit):
                widget.setPlainText(value)
            else:
                widget.setText(value)


class InfoPanel(QWidget):
    def __init__(self, title: str, description: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        text = QLabel(description)
        text.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addStretch()


class GovernancePage(Page):
    def __init__(
        self, session: Session, project: ProjectModel, methodology: PM2Configuration
    ) -> None:
        super().__init__()
        self.session, self.project, self.methodology = session, project, methodology
        layout = QVBoxLayout(self)
        title = QLabel("Gouvernance")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        team_widget = QWidget()
        team_layout = QVBoxLayout(team_widget)
        team_toolbar = QHBoxLayout()
        add_member = QPushButton("Ajouter une personne et un rôle")
        add_member.clicked.connect(self._add_member)
        team_toolbar.addWidget(add_member)
        team_toolbar.addStretch()
        team_layout.addLayout(team_toolbar)
        self.team = QTableWidget(0, 4)
        self.team.setHorizontalHeaderLabels(["Personne", "Rôle", "Organisation", "Actif"])
        self.team.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        team_layout.addWidget(self.team)
        self.tabs.addTab(team_widget, "Équipe & rôles")
        stakeholder_widget = QWidget()
        stakeholder_layout = QVBoxLayout(stakeholder_widget)
        buttons = QHBoxLayout()
        add_stakeholder = QPushButton("Ajouter une partie prenante")
        add_stakeholder.clicked.connect(self._add_stakeholder)
        buttons.addWidget(add_stakeholder)
        buttons.addStretch()
        stakeholder_layout.addLayout(buttons)
        self.stakeholders = QTableWidget(0, 5)
        self.stakeholders.setHorizontalHeaderLabels(
            ["Nom", "Organisation", "Fonction", "Intérêt", "Influence"]
        )
        self.stakeholders.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        stakeholder_layout.addWidget(self.stakeholders)
        self.tabs.addTab(stakeholder_widget, "Parties prenantes")
        ram_widget = QWidget()
        ram_layout = QVBoxLayout(ram_widget)
        ram_toolbar = QHBoxLayout()
        assign_ram = QPushButton("Affecter R / Cm / S / C / I")
        assign_ram.clicked.connect(self._assign_ram)
        ram_toolbar.addWidget(assign_ram)
        ram_toolbar.addStretch()
        ram_layout.addLayout(ram_toolbar)
        self.ram = QTableWidget()
        self.ram.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ram_layout.addWidget(self.ram)
        self.tabs.addTab(ram_widget, "RCmSCI / RAM")
        self.tabs.addTab(
            InfoPanel(
                "Décisions de gouvernance",
                "Les décisions sont gérées dans le registre des décisions.",
            ),
            "Décisions",
        )
        self.reload()

    def _add_member(self) -> None:
        name, ok = QInputDialog.getText(self, "Membre de l’équipe", "Nom *")
        if not ok or not name.strip():
            return
        roles = [*self.methodology.roles.standard, *self.methodology.roles.support]
        labels = [f"{role.code} — {role.name}" for role in roles]
        selected, ok = QInputDialog.getItem(self, "Rôle PM²", "Rôle", labels, 0, False)
        if not ok:
            return
        role_code = roles[labels.index(selected)].code
        try:
            service = GovernanceService(self.session)
            person = service.add_person(name=name.strip())
            service.assign_role(self.project.id, person.id, role_code)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Affectation impossible", str(exc))

    def _assign_ram(self) -> None:
        activities = self.methodology.ram_matrix["activities"]
        activity_labels = [f"{code} — {value['name']}" for code, value in activities.items()]
        activity, ok = QInputDialog.getItem(
            self, "Affectation RCmSCI", "Activité / artefact", activity_labels, 0, False
        )
        if not ok:
            return
        subject_id = activity.split(" — ", 1)[0]
        roles = [*self.methodology.roles.standard, *self.methodology.roles.support]
        role_labels = [f"{role.code} — {role.name}" for role in roles]
        role, ok = QInputDialog.getItem(self, "Affectation RCmSCI", "Rôle", role_labels, 0, False)
        if not ok:
            return
        responsibility, ok = QInputDialog.getItem(
            self, "Affectation RCmSCI", "Responsabilité", ["R", "Cm", "S", "C", "I"], 0, False
        )
        if not ok:
            return
        try:
            ResponsibilityService(self.session).assign(
                self.project.id,
                "activity",
                subject_id,
                role.split(" — ", 1)[0],
                responsibility,
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Affectation refusée", str(exc))

    def _add_stakeholder(self) -> None:
        name, ok = QInputDialog.getText(self, "Partie prenante", "Nom *")
        if not ok or not name.strip():
            return
        organisation, ok = QInputDialog.getText(self, "Partie prenante", "Organisation")
        if not ok:
            return
        try:
            GovernanceService(self.session).add_stakeholder(
                self.project.id, name.strip(), organisation=organisation.strip()
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Ajout impossible", str(exc))

    def reload(self) -> None:
        assignments = self.session.execute(
            select(ProjectRoleAssignmentModel, RoleModel)
            .join(RoleModel, ProjectRoleAssignmentModel.role_code == RoleModel.code)
            .where(ProjectRoleAssignmentModel.project_id == self.project.id)
        ).all()
        self.team.setRowCount(len(assignments))
        for row, (assignment, role) in enumerate(assignments):
            person = assignment.person
            for column, value in enumerate(
                (
                    person.name,
                    f"{role.code} — {role.name}",
                    person.organisation or "",
                    "Oui" if assignment.active else "Non",
                )
            ):
                self.team.setItem(row, column, QTableWidgetItem(value))
        stakeholders = self.session.scalars(
            select(StakeholderModel).where(StakeholderModel.project_id == self.project.id)
        ).all()
        self.stakeholders.setRowCount(len(stakeholders))
        for row, stakeholder in enumerate(stakeholders):
            for column, value in enumerate(
                (
                    stakeholder.name,
                    stakeholder.organisation,
                    stakeholder.function,
                    stakeholder.interest,
                    stakeholder.influence,
                )
            ):
                self.stakeholders.setItem(row, column, QTableWidgetItem(str(value or "")))
        columns = self.methodology.ram_matrix["columns"]
        activities = self.methodology.ram_matrix["activities"]
        overrides = {
            (item.subject_id, item.role_code): item.responsibility_type
            for item in self.session.scalars(
                select(ResponsibilityAssignmentModel).where(
                    ResponsibilityAssignmentModel.project_id == self.project.id,
                    ResponsibilityAssignmentModel.subject_type == "activity",
                )
            )
        }
        self.ram.setColumnCount(len(columns) + 1)
        self.ram.setHorizontalHeaderLabels(["Activité", *columns])
        self.ram.setRowCount(len(activities))
        for row, (code, activity) in enumerate(activities.items()):
            self.ram.setItem(row, 0, QTableWidgetItem(f"{code} — {activity['name']}"))
            for col, role in enumerate(columns, 1):
                configured = str(activity["responsibilities"].get(role, ""))
                self.ram.setItem(
                    row, col, QTableWidgetItem(overrides.get((code, role), configured))
                )
        self.ram.resizeColumnsToContents()


class WorkPlanPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        title = QLabel("Plan de travail · WBS")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        add_button = QPushButton("Nouvel élément")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add)
        edit_button = QPushButton("Modifier / renommer")
        edit_button.clicked.connect(self._edit)
        up_button = QPushButton("Monter")
        up_button.clicked.connect(lambda: self._move_sibling(-1))
        down_button = QPushButton("Descendre")
        down_button.clicked.connect(lambda: self._move_sibling(1))
        indent_button = QPushButton("Indenter")
        indent_button.clicked.connect(self._indent)
        outdent_button = QPushButton("Désindenter")
        outdent_button.clicked.connect(self._outdent)
        dependency_button = QPushButton("Dépendance +")
        dependency_button.setToolTip("Ajouter une dépendance entre deux tâches")
        dependency_button.clicked.connect(self._add_dependency)
        remove_dependency_button = QPushButton("Dépendance −")
        remove_dependency_button.setToolTip("Retirer la dépendance sélectionnée")
        remove_dependency_button.clicked.connect(self._remove_dependency)
        archive_button = QPushButton("Archiver")
        archive_button.clicked.connect(self._archive)
        primary_actions = QHBoxLayout()
        primary_actions.addWidget(add_button)
        primary_actions.addWidget(edit_button)
        primary_actions.addWidget(archive_button)
        primary_actions.addStretch()
        layout.addLayout(primary_actions)
        structure_actions = QHBoxLayout()
        structure_actions.addWidget(up_button)
        structure_actions.addWidget(down_button)
        structure_actions.addWidget(indent_button)
        structure_actions.addWidget(outdent_button)
        structure_actions.addWidget(dependency_button)
        structure_actions.addWidget(remove_dependency_button)
        structure_actions.addStretch()
        layout.addLayout(structure_actions)
        splitter = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            ["Code / nom", "Type", "Statut", "Début", "Fin", "Progression", "Coût"]
        )
        self.tree.setAlternatingRowColors(True)
        self.tree.itemSelectionChanged.connect(self._show_details)
        splitter.addWidget(self.tree)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Sélectionnez un élément pour afficher ses détails et ses relations."
        )
        splitter.addWidget(self.details)
        splitter.setSizes([800, 280])
        layout.addWidget(splitter)
        gantt_group = QGroupBox("Gantt simple")
        gantt_layout = QVBoxLayout(gantt_group)
        self.gantt = QTableWidget(0, 5)
        self.gantt.setHorizontalHeaderLabels(["Tâche", "Début", "Fin", "Durée", "Représentation"])
        self.gantt.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.gantt.setMaximumHeight(240)
        self.gantt.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        gantt_layout.addWidget(self.gantt)
        self.dependencies = QTableWidget(0, 4)
        self.dependencies.setHorizontalHeaderLabels(
            ["Prédécesseur", "Type", "Successeur", "Décalage"]
        )
        self.dependencies.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dependencies.setMaximumHeight(130)
        self.dependencies.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        gantt_layout.addWidget(QLabel("Dépendances"))
        gantt_layout.addWidget(self.dependencies)
        layout.addWidget(gantt_group)
        self.reload()

    def _selected_node(self) -> WbsNodeModel | None:
        selected = self.tree.currentItem()
        if not selected:
            return None
        return self.session.get(WbsNodeModel, selected.data(0, Qt.ItemDataRole.UserRole))

    def _add(self) -> None:
        dialog = WbsNodeDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        selected = self.tree.currentItem()
        parent_id = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        try:
            node = WorkPlanService(self.session).create_node(
                self.project.id,
                values.pop("code"),
                values.pop("name"),
                node_type=values.pop("node_type"),
                parent_id=parent_id,
                description=values.pop("description"),
            )
            if node.node_type in {"task", "milestone"}:
                WorkPlanService(self.session).create_task(node.id, **values)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Création impossible", str(exc))

    def _edit(self) -> None:
        node = self._selected_node()
        if node is None:
            return
        dialog = WbsNodeDialog(self, node=node)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        values.pop("node_type")
        try:
            WorkPlanService(self.session).update_node(node.id, **values)
            self.session.commit()
            self.reload(select_id=node.id)
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Modification impossible", str(exc))

    def _move_sibling(self, offset: int) -> None:
        node = self._selected_node()
        if node is None:
            return
        self._run_wbs_action(lambda service: service.move_sibling(node.id, offset), node.id)

    def _indent(self) -> None:
        node = self._selected_node()
        if node:
            self._run_wbs_action(lambda service: service.indent(node.id), node.id)

    def _outdent(self) -> None:
        node = self._selected_node()
        if node:
            self._run_wbs_action(lambda service: service.outdent(node.id), node.id)

    def _run_wbs_action(self, operation: Callable[[WorkPlanService], None], select_id: str) -> None:
        try:
            operation(WorkPlanService(self.session))
            self.session.commit()
            self.reload(select_id=select_id)
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Opération WBS refusée", str(exc))

    def _add_dependency(self) -> None:
        successor_node = self._selected_node()
        if successor_node is None or successor_node.task is None:
            QMessageBox.information(
                self, "Dépendance", "Sélectionnez la tâche successeur dans la WBS."
            )
            return
        candidates = self.session.scalars(
            select(TaskModel)
            .join(WbsNodeModel)
            .where(
                WbsNodeModel.project_id == self.project.id,
                TaskModel.id != successor_node.task.id,
            )
        ).all()
        if not candidates:
            QMessageBox.information(self, "Dépendance", "Créez au moins une autre tâche.")
            return
        labels = [f"{item.wbs_node.code} — {item.wbs_node.name}" for item in candidates]
        selected, ok = QInputDialog.getItem(
            self, "Nouvelle dépendance", "Tâche prédécesseur", labels, 0, False
        )
        if not ok:
            return
        dependency_type, ok = QInputDialog.getItem(
            self, "Nouvelle dépendance", "Type", ["FS", "SS", "FF", "SF"], 0, False
        )
        if not ok:
            return
        predecessor = candidates[labels.index(selected)]
        try:
            WorkPlanService(self.session).add_dependency(
                predecessor.id, successor_node.task.id, dependency_type
            )
            self.session.commit()
            self.reload(select_id=successor_node.id)
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Dépendance refusée", str(exc))

    def _archive(self) -> None:
        node = self._selected_node()
        if node is None:
            return
        answer = QMessageBox.question(
            self,
            "Archiver",
            f"Archiver {node.code} — {node.name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            WorkPlanService(self.session).archive_node(node.id)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Archivage impossible", str(exc))

    def _remove_dependency(self) -> None:
        row = self.dependencies.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Dépendance", "Sélectionnez une dépendance dans le tableau."
            )
            return
        dependency_id = self.dependencies.item(row, 0).data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self,
            "Retirer la dépendance",
            "Supprimer cette dépendance ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_wbs_action(lambda service: service.remove_dependency(dependency_id), "")

    def _show_details(self) -> None:
        selected = self.tree.currentItem()
        if not selected:
            self.details.clear()
            return
        node = self.session.get(WbsNodeModel, selected.data(0, Qt.ItemDataRole.UserRole))
        if not node:
            return
        task = node.task
        lines = [
            f"{node.code} — {node.name}",
            f"Type : {node.node_type}",
            node.description or "Aucune description.",
        ]
        if task:
            lines.extend(
                [
                    "",
                    f"Statut : {task.status}",
                    f"Dates : {task.planned_start or '—'} → {task.planned_end or '—'}",
                    f"Effort : {task.planned_effort}",
                    f"Coût : {task.planned_cost}",
                    f"Avancement : {task.progress_percent} %",
                    "",
                    "Relations / Traçabilité disponibles dans la page dédiée.",
                ]
            )
        self.details.setPlainText("\n".join(lines))

    def reload(self, select_id: str | None = None) -> None:
        self.tree.clear()
        nodes = self.session.scalars(
            select(WbsNodeModel)
            .where(WbsNodeModel.project_id == self.project.id, WbsNodeModel.archived.is_(False))
            .order_by(WbsNodeModel.sequence, WbsNodeModel.code)
        ).all()
        items: dict[str, QTreeWidgetItem] = {}
        for node in nodes:
            task = node.task
            item = QTreeWidgetItem(
                [
                    f"{node.code} — {node.name}",
                    node.node_type,
                    task.status if task else "",
                    str(task.planned_start or "") if task else "",
                    str(task.planned_end or "") if task else "",
                    f"{task.progress_percent} %" if task else "",
                    str(task.planned_cost) if task else "",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            items[node.id] = item
        for node in nodes:
            item = items[node.id]
            if node.parent_id and node.parent_id in items:
                items[node.parent_id].addChild(item)
            else:
                self.tree.addTopLevelItem(item)
        self.tree.expandAll()
        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)
        scheduled = [node for node in nodes if node.task and node.task.planned_start]
        self.gantt.setRowCount(len(scheduled))
        for row, node in enumerate(scheduled):
            task = node.task
            assert task is not None
            duration = (
                (task.planned_end - task.planned_start).days + 1
                if task.planned_end and task.planned_start
                else 1
            )
            values = (
                f"{node.code} — {node.name}",
                str(task.planned_start or ""),
                str(task.planned_end or ""),
                f"{duration} j",
                "█" * min(duration, 40),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 4:
                    item.setForeground(QColor("#2f6b91"))
                self.gantt.setItem(row, column, item)
        task_nodes = {node.task.id: node for node in nodes if node.task}
        dependencies = (
            self.session.scalars(
                select(TaskDependencyModel).where(
                    TaskDependencyModel.predecessor_task_id.in_(task_nodes),
                    TaskDependencyModel.successor_task_id.in_(task_nodes),
                )
            ).all()
            if task_nodes
            else []
        )
        self.dependencies.setRowCount(len(dependencies))
        for row, dependency in enumerate(dependencies):
            predecessor = task_nodes[dependency.predecessor_task_id]
            successor = task_nodes[dependency.successor_task_id]
            values = (
                f"{predecessor.code} — {predecessor.name}",
                dependency.dependency_type,
                f"{successor.code} — {successor.name}",
                f"{dependency.lag_days} j",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, dependency.id)
                self.dependencies.setItem(row, column, item)
        if select_id and select_id in items:
            self.tree.setCurrentItem(items[select_id])


class CoreDataPage(Page):
    """Éditeur des objets structurés qui alimentent artefacts et traçabilité."""

    CONFIG: dict[str, tuple[str, Any, tuple[str, ...]]] = {
        "requirements": (
            "Exigences",
            RequirementModel,
            ("code", "title", "status", "priority", "source"),
        ),
        "deliverables": (
            "Livrables",
            DeliverableModel,
            ("code", "name", "status", "owner", "planned_date"),
        ),
        "criteria": (
            "Critères d’acceptation",
            AcceptanceCriterionModel,
            ("code", "description", "status", "mandatory"),
        ),
        "tests": (
            "Tests d’acceptation",
            AcceptanceTestModel,
            ("code", "description", "expected_result", "outcome"),
        ),
        "quality": (
            "Contrôles qualité",
            QualityControlModel,
            ("code", "title", "status", "owner", "control_date"),
        ),
        "transition": (
            "Transition",
            TransitionActivityModel,
            ("code", "title", "status", "owner", "task_id"),
        ),
        "implementation": (
            "Mise en œuvre",
            ImplementationActivityModel,
            ("code", "title", "status", "owner", "task_id"),
        ),
        "meetings": ("Réunions", MeetingModel, ("code", "title", "status", "scheduled_at")),
    }

    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Besoins, livrables & opérations")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        add = QPushButton("Créer")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        transition = QPushButton("Changer le statut")
        transition.clicked.connect(self._transition)
        link = QPushButton("Relier l’exigence")
        link.clicked.connect(self._link_requirement)
        heading.addWidget(add)
        heading.addWidget(transition)
        heading.addWidget(link)
        layout.addLayout(heading)
        self.tabs = QTabWidget()
        self.tables: dict[str, QTableWidget] = {}
        for key, (label, _model, columns) in self.CONFIG.items():
            table = QTableWidget(0, len(columns))
            table.setHorizontalHeaderLabels(
                [column.replace("_", " ").capitalize() for column in columns]
            )
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.tabs.addTab(table, label)
            self.tables[key] = table
        layout.addWidget(self.tabs)
        note = QLabel(
            "Chaque fiche est persistée, auditée si critique et peut être connectée dans Traçabilité."
        )
        note.setObjectName("pageSubtitle")
        layout.addWidget(note)
        self.reload()

    def _current_key(self) -> str:
        return list(self.CONFIG)[self.tabs.currentIndex()]

    def _selected_entity(self) -> Any | None:
        key = self._current_key()
        table = self.tables[key]
        row = table.currentRow()
        if row < 0:
            return None
        entity_id = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return self.session.get(self.CONFIG[key][1], entity_id)

    def _transition(self) -> None:
        key = self._current_key()
        kinds = {
            "requirements": "requirement",
            "deliverables": "deliverable",
            "meetings": "meeting",
        }
        kind = kinds.get(key)
        entity = self._selected_entity()
        if not kind or entity is None:
            QMessageBox.information(
                self, "Workflow", "Sélectionnez une exigence, un livrable ou une réunion."
            )
            return
        from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE

        targets = sorted(DEFAULT_WORKFLOW_ENGINE.allowed_targets(kind, entity.status))
        if not targets:
            QMessageBox.information(self, "Workflow", "Aucune transition disponible.")
            return
        target, ok = QInputDialog.getItem(
            self, "Transition", f"État actuel : {entity.status}", targets, 0, False
        )
        if not ok:
            return
        try:
            WorkflowService(self.session).transition(kind, entity.id, target)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Transition refusée", str(exc))

    def _link_requirement(self) -> None:
        if self._current_key() != "requirements":
            QMessageBox.information(
                self, "Traçabilité", "Ouvrez l’onglet Exigences et sélectionnez une ligne."
            )
            return
        requirement = self._selected_entity()
        if requirement is None:
            return
        target_kind, ok = QInputDialog.getItem(
            self, "Relier l’exigence", "Type de cible", ["Tâche", "Livrable"], 0, False
        )
        if not ok:
            return
        if target_kind == "Tâche":
            targets = self.session.scalars(
                select(TaskModel)
                .join(WbsNodeModel)
                .where(WbsNodeModel.project_id == self.project.id)
            ).all()
            labels = [(f"{item.wbs_node.code} — {item.wbs_node.name}", item.id) for item in targets]
        else:
            targets = self.session.scalars(
                select(DeliverableModel).where(DeliverableModel.project_id == self.project.id)
            ).all()
            labels = [(f"{item.code} — {item.name}", item.id) for item in targets]
        target_id = self._choose("Relier l’exigence", "Cible", labels)
        if not target_id:
            return
        try:
            service = RequirementService(self.session)
            trace = TraceabilityService(self.session)
            if target_kind == "Tâche":
                service.link_task(requirement.id, target_id)
                trace.link(
                    self.project.id,
                    "requirement",
                    requirement.id,
                    "task",
                    target_id,
                    "implements",
                )
            else:
                service.link_deliverable(requirement.id, target_id)
                trace.link(
                    self.project.id,
                    "requirement",
                    requirement.id,
                    "deliverable",
                    target_id,
                    "produces",
                )
            self.session.commit()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Lien impossible", str(exc))

    def _text(self, title: str, label: str, *, required: bool = True) -> str | None:
        value, ok = QInputDialog.getText(self, title, label)
        if not ok:
            return None
        value = value.strip()
        if required and not value:
            QMessageBox.warning(self, "Donnée requise", f"{label.rstrip('* ')} est obligatoire.")
            return None
        return value

    def _choose(self, title: str, label: str, values: list[tuple[str, str]]) -> str | None:
        if not values:
            QMessageBox.warning(self, title, "Aucun élément parent disponible.")
            return None
        labels = [item[0] for item in values]
        selected, ok = QInputDialog.getItem(self, title, label, labels, 0, False)
        return dict(values)[selected] if ok else None

    def _add(self) -> None:
        key = self._current_key()
        try:
            if key == "requirements":
                self._add_requirement()
            elif key == "deliverables":
                self._add_deliverable()
            elif key == "criteria":
                self._add_criterion()
            elif key == "tests":
                self._add_acceptance_test()
            elif key == "quality":
                self._add_quality_control()
            elif key in {"transition", "implementation"}:
                self._add_transition(key == "implementation")
            else:
                self._add_meeting()
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Création impossible", str(exc))

    def _add_requirement(self) -> None:
        code = self._text("Nouvelle exigence", "Code *")
        title = self._text("Nouvelle exigence", "Titre *") if code else None
        if not code or not title:
            return
        source = self._text("Nouvelle exigence", "Source", required=False)
        priority, ok = QInputDialog.getItem(
            self,
            "Nouvelle exigence",
            "Priorité",
            ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            1,
            False,
        )
        if not ok:
            return
        method = self._text("Nouvelle exigence", "Méthode de vérification", required=False)
        RequirementService(self.session).create(
            self.project.id,
            code,
            title,
            source=source or None,
            priority=priority,
            verification_method=method or None,
        )

    def _add_deliverable(self) -> None:
        code = self._text("Nouveau livrable", "Code *")
        name = self._text("Nouveau livrable", "Nom *") if code else None
        if not code or not name:
            return
        owner = self._text("Nouveau livrable", "Responsable", required=False)
        DeliverableService(self.session).create(self.project.id, code, name, owner=owner or None)

    def _add_criterion(self) -> None:
        deliverables = self.session.scalars(
            select(DeliverableModel).where(DeliverableModel.project_id == self.project.id)
        ).all()
        deliverable_id = self._choose(
            "Critère d’acceptation",
            "Livrable",
            [(f"{item.code} — {item.name}", item.id) for item in deliverables],
        )
        code = self._text("Critère d’acceptation", "Code *") if deliverable_id else None
        description = self._text("Critère d’acceptation", "Description *") if code else None
        if deliverable_id and code and description:
            AcceptanceService(self.session).add_criterion(deliverable_id, code, description)

    def _add_acceptance_test(self) -> None:
        criteria = self.session.scalars(
            select(AcceptanceCriterionModel)
            .join(DeliverableModel)
            .where(DeliverableModel.project_id == self.project.id)
        ).all()
        criterion_id = self._choose(
            "Test d’acceptation",
            "Critère",
            [(f"{item.code} — {item.description[:60]}", item.id) for item in criteria],
        )
        code = self._text("Test d’acceptation", "Code *") if criterion_id else None
        description = self._text("Test d’acceptation", "Description *") if code else None
        expected = self._text("Test d’acceptation", "Résultat attendu *") if description else None
        if criterion_id and code and description and expected:
            AcceptanceService(self.session).add_test(criterion_id, code, description, expected)

    def _add_quality_control(self) -> None:
        code = self._text("Contrôle qualité", "Code *")
        title = self._text("Contrôle qualité", "Titre *") if code else None
        if code and title:
            owner = self._text("Contrôle qualité", "Responsable", required=False)
            QualityService(self.session).create_control(
                self.project.id, code, title, owner=owner or None
            )

    def _add_transition(self, implementation: bool) -> None:
        label = "Mise en œuvre" if implementation else "Transition"
        code = self._text(label, "Code *")
        title = self._text(label, "Titre *") if code else None
        if code and title:
            owner = self._text(label, "Responsable", required=False)
            TransitionService(self.session).create(
                self.project.id,
                code,
                title,
                owner=owner or None,
                implementation=implementation,
            )

    def _add_meeting(self) -> None:
        code = self._text("Nouvelle réunion", "Code *")
        title = self._text("Nouvelle réunion", "Titre *") if code else None
        if code and title:
            MeetingService(self.session).create(self.project.id, code, title)

    def reload(self) -> None:
        for key, (_label, model, columns) in self.CONFIG.items():
            if key == "criteria":
                statement = (
                    select(model)
                    .join(DeliverableModel)
                    .where(DeliverableModel.project_id == self.project.id)
                )
            elif key == "tests":
                statement = (
                    select(model)
                    .join(AcceptanceCriterionModel)
                    .join(DeliverableModel)
                    .where(DeliverableModel.project_id == self.project.id)
                )
            else:
                statement = select(model).where(model.project_id == self.project.id)
            rows = self.session.scalars(statement).all()
            table = self.tables[key]
            table.setRowCount(len(rows))
            for row_index, entity in enumerate(rows):
                for column_index, column in enumerate(columns):
                    item = QTableWidgetItem(str(getattr(entity, column) or ""))
                    if column_index == 0:
                        item.setData(Qt.ItemDataRole.UserRole, entity.id)
                    table.setItem(row_index, column_index, item)


REGISTER_CONFIG: dict[str, tuple[str, Any, list[str]]] = {
    "risk": ("Risques", RiskModel, ["code", "title", "status", "owner", "score", "due_date"]),
    "issue": (
        "Problèmes",
        IssueModel,
        ["code", "title", "status", "owner", "priority", "due_date"],
    ),
    "decision": (
        "Décisions",
        DecisionModel,
        ["code", "title", "status", "decision_owner", "decision_date"],
    ),
    "change": (
        "Modifications",
        ChangeModel,
        ["code", "title", "status", "requester", "priority", "request_date"],
    ),
}


class RegisterTab(QWidget):
    changed = Signal()

    def __init__(self, session: Session, project: ProjectModel, kind: str) -> None:
        super().__init__()
        self.session, self.project, self.kind = session, project, kind
        self.title, self.model, self.columns = REGISTER_CONFIG[kind]
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher…")
        self.search.textChanged.connect(self.reload)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tous les statuts", "")
        self.status_filter.currentIndexChanged.connect(self.reload)
        add = QPushButton("Créer")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        edit = QPushButton("Modifier")
        edit.clicked.connect(self._edit)
        transition = QPushButton("Changer le statut")
        transition.clicked.connect(self._transition)
        details = QPushButton("Fiche détaillée")
        details.clicked.connect(self._details)
        archive = QPushButton("Archiver")
        archive.clicked.connect(self._archive)
        toolbar.addWidget(self.search)
        toolbar.addWidget(self.status_filter)
        toolbar.addStretch()
        toolbar.addWidget(add)
        toolbar.addWidget(edit)
        toolbar.addWidget(transition)
        toolbar.addWidget(details)
        toolbar.addWidget(archive)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(
            [FIELD_LABELS.get(name, name.replace("_", " ").capitalize()) for name in self.columns]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._details)
        layout.addWidget(self.table)
        self.reload()

    def _selected_entity(self) -> Any | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        entity_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return self.session.get(self.model, entity_id)

    def _add(self) -> None:
        dialog = RegisterItemDialog(self.kind, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            RegisterService(self.session).create(self.kind, self.project.id, **dialog.values())
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Création impossible", str(exc))

    def _transition(self) -> None:
        entity = self._selected_entity()
        if not entity:
            return
        from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE

        targets = sorted(DEFAULT_WORKFLOW_ENGINE.allowed_targets(self.kind, entity.status))
        if not targets:
            QMessageBox.information(
                self, "Workflow", "Aucune transition disponible depuis cet état."
            )
            return
        target, ok = QInputDialog.getItem(
            self, "Transition", f"État actuel : {entity.status}\nNouvel état", targets, 0, False
        )
        if not ok:
            return
        try:
            workflow = WorkflowService(self.session)
            if self.kind == "change" and entity.status == "APPROVAL" and target == "APPROVED":
                approver, accepted = QInputDialog.getText(
                    self, "Approbation formelle", "Approbateur *"
                )
                if not accepted or not approver.strip():
                    return
                workflow.approve_change(entity.id, approver.strip())
            else:
                workflow.transition(self.kind, entity.id, target)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Transition refusée", str(exc))

    def _edit(self) -> None:
        entity = self._selected_entity()
        if entity is None:
            return
        table_name = str(self.model.__tablename__)
        dialog = EntityEditDialog(
            self.session,
            table_name,
            entity,
            project_id=self.project.id,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            EntityCrudService(self.session, self.project.id).update(
                table_name, entity.id, dialog.values()
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Modification impossible", str(exc))

    def _archive(self) -> None:
        entity = self._selected_entity()
        if entity is None:
            return
        answer = QMessageBox.question(
            self,
            "Archiver",
            f"Archiver {entity.code} — {entity.title} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            EntityCrudService(self.session, self.project.id).remove(
                str(self.model.__tablename__), entity.id
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Archivage impossible", str(exc))

    def _details(self, *_args: Any) -> None:
        entity = self._selected_entity()
        if entity is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Fiche détaillée — {entity.code}")
        dialog.resize(1180, 760)
        dialog_layout = QVBoxLayout(dialog)
        catalog = EntityCatalogPage(self.session, self.project.id)
        selector_index = catalog.selector.findData(str(self.model.__tablename__))
        catalog.selector.setCurrentIndex(selector_index)
        for row in range(catalog.table.rowCount()):
            if catalog.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == entity.id:
                catalog.table.selectRow(row)
                break
        catalog.changed.connect(self.reload)
        dialog_layout.addWidget(catalog)
        close = QPushButton("Fermer")
        close.clicked.connect(dialog.accept)
        dialog_layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def reload(self) -> None:
        statement = select(self.model).where(
            self.model.project_id == self.project.id,
            self.model.archived.is_(False),
        )
        search = self.search.text().strip().lower()
        rows = list(self.session.scalars(statement).all())
        if search:
            rows = [row for row in rows if search in f"{row.code} {row.title}".lower()]
        status = self.status_filter.currentData()
        if status:
            rows = [row for row in rows if row.status == status]
        statuses = sorted({row.status for row in rows})
        existing = {
            self.status_filter.itemData(index) for index in range(self.status_filter.count())
        }
        for value in statuses:
            if value not in existing:
                self.status_filter.addItem(value, value)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, entity in enumerate(rows):
            for column_index, name in enumerate(self.columns):
                item = QTableWidgetItem(str(getattr(entity, name) or ""))
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, entity.id)
                self.table.setItem(row_index, column_index, item)
        self.table.setSortingEnabled(True)


class RegistersPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Registres PM²")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        self.register_tabs: list[RegisterTab] = []
        for kind in ("risk", "issue", "decision", "change"):
            tab = RegisterTab(session, project, kind)
            tab.changed.connect(self.changed)
            self.tabs.addTab(tab, REGISTER_CONFIG[kind][0])
            self.register_tabs.append(tab)
        layout.addWidget(self.tabs)

    def reload(self) -> None:
        for tab in self.register_tabs:
            tab.reload()


class GatesPage(Page):
    def __init__(
        self, session: Session, project: ProjectModel, methodology: PM2Configuration
    ) -> None:
        super().__init__()
        self.session, self.project, self.methodology = session, project, methodology
        self.service = GateService(session, methodology)
        layout = QVBoxLayout(self)
        title = QLabel("Readiness gates")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        self.checkboxes: dict[str, list[tuple[QCheckBox, str]]] = {}
        self.status_labels: dict[str, QLabel] = {}
        for definition in methodology.gates:
            widget = QWidget()
            gate_layout = QVBoxLayout(widget)
            summary = QLabel(f"{definition.label}\n{definition.from_phase} → {definition.to_phase}")
            summary.setObjectName("sectionTitle")
            gate_layout.addWidget(summary)
            status = QLabel()
            self.status_labels[definition.code] = status
            gate_layout.addWidget(status)
            group = QGroupBox("Checklist")
            group_layout = QVBoxLayout(group)
            review = self.service.get_or_create(project.id, definition.code)
            boxes: list[tuple[QCheckBox, str]] = []
            for item in self.service.checklist(review.id):
                box = QCheckBox(
                    f"{item.item_code} — {item.description}" + (" *" if item.required else "")
                )
                box.setChecked(item.satisfied)
                box.stateChanged.connect(
                    lambda state, item_id=item.id: self._set_item(item_id, bool(state))
                )
                group_layout.addWidget(box)
                boxes.append((box, item.id))
            self.checkboxes[definition.code] = boxes
            gate_layout.addWidget(group)
            action_layout = QHBoxLayout()
            decide = QPushButton("Enregistrer une décision")
            decide.clicked.connect(lambda _checked=False, code=definition.code: self._decide(code))
            action_layout.addStretch()
            action_layout.addWidget(decide)
            gate_layout.addLayout(action_layout)
            gate_layout.addStretch()
            self.tabs.addTab(widget, definition.name)
        self.session.commit()
        layout.addWidget(self.tabs)
        self.reload()

    def _set_item(self, item_id: str, satisfied: bool) -> None:
        try:
            self.service.set_item(item_id, satisfied)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Mise à jour impossible", str(exc))

    def _decide(self, gate_code: str) -> None:
        review = self.service.get_or_create(self.project.id, gate_code)
        options = [item.value for item in GateDecisionType]
        decision, ok = QInputDialog.getItem(self, "Décision de gate", "Décision", options, 0, False)
        if not ok:
            return
        decider, ok = QInputDialog.getText(self, "Décision de gate", "Décideur *")
        if not ok:
            return
        try:
            self.service.decide(review.id, decision, decider)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Décision refusée", str(exc))

    def reload(self) -> None:
        self.session.refresh(self.project)
        for definition in self.methodology.gates:
            review = self.service.get_or_create(self.project.id, definition.code)
            self.status_labels[definition.code].setText(
                f"Phase actuelle : {self.project.current_phase} · Statut : {review.status}"
            )
            for box, item_id in self.checkboxes[definition.code]:
                item = self.session.get(
                    __import__(
                        "pm2.infrastructure.orm", fromlist=["GateChecklistItemModel"]
                    ).GateChecklistItemModel,
                    item_id,
                )
                if item:
                    box.blockSignals(True)
                    box.setChecked(item.satisfied)
                    box.blockSignals(False)


class TraceabilityPage(Page):
    navigate_requested = Signal(str)

    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Traçabilité")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        add = QPushButton("Créer un lien")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        remove = QPushButton("Supprimer le lien")
        remove.clicked.connect(self._remove)
        navigate = QPushButton("Aller à la cible")
        navigate.clicked.connect(self._navigate)
        heading.addWidget(add)
        heading.addWidget(navigate)
        heading.addWidget(remove)
        layout.addLayout(heading)
        self.filter = QComboBox()
        self.filter.addItem("Toutes les relations", "")
        self.filter.addItems(sorted(TraceabilityService.RELATION_TYPES))
        self.filter.currentIndexChanged.connect(self.reload)
        layout.addWidget(self.filter)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Source", "Relation", "Cible", "Critique", "Créé le"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.reload()

    def _navigate(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        target_type = self.table.item(row, 2).data(Qt.ItemDataRole.UserRole)
        destinations = {
            "task": "Plan de travail",
            "wbs_node": "Plan de travail",
            "requirement": "Données métier",
            "deliverable": "Données métier",
            "acceptance_test": "Données métier",
            "transition_activity": "Données métier",
            "risk": "Registres",
            "issue": "Registres",
            "decision": "Registres",
            "change": "Registres",
            "document": "Documents",
        }
        self.navigate_requested.emit(destinations.get(target_type, "Traçabilité"))

    def _add(self) -> None:
        dialog = TraceLinkDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            TraceabilityService(self.session).link(self.project.id, **dialog.values())
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Lien impossible", str(exc))

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            TraceabilityService(self.session).unlink(
                self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Suppression impossible", str(exc))

    def reload(self) -> None:
        statement = select(TraceLinkModel).where(TraceLinkModel.project_id == self.project.id)
        relation = self.filter.currentData()
        if relation:
            statement = statement.where(TraceLinkModel.relation_type == relation)
        links = self.session.scalars(statement.order_by(TraceLinkModel.created_at.desc())).all()
        self.table.setRowCount(len(links))
        for row, link in enumerate(links):
            values = (
                f"{link.source_type} · {link.source_id}",
                link.relation_type,
                f"{link.target_type} · {link.target_id}",
                "Oui" if link.critical else "Non",
                str(link.created_at),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, link.id)
                if column == 2:
                    item.setData(Qt.ItemDataRole.UserRole, link.target_type)
                self.table.setItem(row, column, item)


class DocumentsPage(Page):
    def __init__(
        self,
        session: Session,
        database: Database,
        project: ProjectModel,
        methodology: PM2Configuration,
        default_output: Path,
    ) -> None:
        super().__init__()
        self.session, self.database, self.project = session, database, project
        self.methodology, self.default_output = methodology, default_output
        self.service = DocumentService(session, methodology)
        self.service.ensure_catalog(project.id)
        self.session.commit()
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Documents & artefacts")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        self.format = QComboBox()
        self.format.addItems(["Markdown", "HTML", "DOCX", "PDF"])
        generate = QPushButton("Générer")
        generate.setObjectName("primaryButton")
        generate.clicked.connect(self._generate)
        preview = QPushButton("Voir le détail")
        preview.clicked.connect(self._open_document_detail)
        open_folder = QPushButton("Ouvrir le dossier")
        open_folder.clicked.connect(self._open_folder)
        bundle = QPushButton("Exporter le projet .pm2")
        bundle.clicked.connect(self._bundle)
        heading.addWidget(self.format)
        heading.addWidget(preview)
        heading.addWidget(generate)
        heading.addWidget(open_folder)
        heading.addWidget(bundle)
        layout.addLayout(heading)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Titre", "Phase", "Requis", "Statut"])
        self.table.setProperty("pm2CustomRowDetail", True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setToolTip(
            "Double-cliquez sur une ligne, ou sélectionnez-la et appuyez sur Entrée, "
            "pour afficher le détail du document."
        )
        self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._load_history)
        self.table.itemActivated.connect(
            lambda item: self._open_document_detail(item.row())
        )
        layout.addWidget(self.table)
        layout.addWidget(QLabel("Historique des versions"))
        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(
            ["Version", "Statut", "Créée le", "Fichier", "Empreinte SHA-256"]
        )
        history_header = self.history.horizontalHeader()
        for column in (0, 1, 2, 4):
            history_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setMaximumHeight(190)
        layout.addWidget(self.history)
        self.reload()

    def _selected_code(self) -> str | None:
        row = self.table.currentRow()
        return self.table.item(row, 0).text() if row >= 0 else None

    def _open_document_detail(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        if row is not None:
            self.table.selectRow(row)
        code = self._selected_code()
        if not code:
            QMessageBox.information(self, "Détail du document", "Sélectionnez un artefact.")
            return
        try:
            document = self.session.scalar(
                select(DocumentModel).where(
                    DocumentModel.project_id == self.project.id,
                    DocumentModel.artifact_code == code,
                )
            )
            definition = self.methodology.artifacts[code]
            schema = ARTIFACT_SCHEMAS[code]
            rendered = self.service.render_html(self.service.context(self.project.id, code))
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Détail — {definition.name}")
            dialog.setProperty("artifactCode", code)
            dialog.resize(1000, 760)
            dialog_layout = QVBoxLayout(dialog)
            title = QLabel(definition.name)
            title.setObjectName("pageTitle")
            metadata = QLabel(
                f"Code : {code}  ·  Phase : {definition.phase}  ·  "
                f"Requis : {'Oui' if definition.required else 'Non'}  ·  "
                f"Statut : {document.status if document else '—'}"
            )
            metadata.setObjectName("pageSubtitle")
            purpose = QLabel(schema.purpose)
            purpose.setWordWrap(True)
            purpose.setObjectName("documentPurpose")
            preview = QTextBrowser(dialog)
            preview.setObjectName("documentDetailContent")
            preview.setHtml(rendered)
            preview.setOpenExternalLinks(False)
            dialog_layout.addWidget(title)
            dialog_layout.addWidget(metadata)
            dialog_layout.addWidget(purpose)
            dialog_layout.addWidget(preview)
            close = QPushButton("Fermer")
            close.clicked.connect(dialog.accept)
            dialog_layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
            dialog.exec()
        except Exception as exc:
            QMessageBox.critical(self, "Détail impossible", str(exc))

    def _preview(self) -> None:
        """Backward-compatible entry point used by existing integrations."""
        self._open_document_detail()

    def _open_folder(self) -> None:
        self.default_output.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.default_output.resolve())))

    def _generate(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Génération", "Sélectionnez un artefact.")
            return
        code = self.table.item(row, 0).text()
        fmt = self.format.currentText().lower()
        suffix = "md" if fmt == "markdown" else fmt
        directory = QFileDialog.getExistingDirectory(
            self, "Dossier d'export", str(self.default_output)
        )
        if not directory:
            return
        try:
            result = ExportService(self.session, self.database, self.methodology).generate_artifact(
                self.project.id, code, suffix, Path(directory)
            )
            self.session.commit()
            self.reload()
            QMessageBox.information(self, "Artefact généré", f"Fichier créé :\n{result.path}")
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Génération impossible", str(exc))

    def _bundle(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le projet",
            str(self.default_output / f"{self.project.reference}.pm2"),
            "Projet PM² (*.pm2)",
        )
        if not path:
            return
        try:
            output = ExportService(
                self.session, self.database, self.methodology
            ).generate_project_bundle(self.project.id, Path(path))
            QMessageBox.information(self, "Projet exporté", f"Archive créée :\n{output}")
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Export impossible", str(exc))

    def reload(self) -> None:
        selected_code = self._selected_code()
        documents = self.service.ensure_catalog(self.project.id)
        self.table.setRowCount(len(documents))
        for row, document in enumerate(documents):
            definition = self.methodology.artifacts[document.artifact_code]
            for column, value in enumerate(
                (
                    document.artifact_code,
                    document.title,
                    definition.phase,
                    "Oui" if definition.required else "Non",
                    document.status,
                )
            ):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
            if document.artifact_code == selected_code:
                self.table.selectRow(row)
        if self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)
        self._load_history()

    def _load_history(self) -> None:
        code = self._selected_code()
        if not code:
            self.history.setRowCount(0)
            return
        document = self.session.scalar(
            select(DocumentModel).where(
                DocumentModel.project_id == self.project.id,
                DocumentModel.artifact_code == code,
            )
        )
        versions = (
            self.session.scalars(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document.id)
                .order_by(DocumentVersionModel.created_at.desc())
            ).all()
            if document
            else []
        )
        self.history.setRowCount(len(versions))
        for row, version in enumerate(versions):
            for column, value in enumerate(
                (
                    version.version,
                    version.status,
                    version.created_at,
                    version.file_path,
                    version.content_hash,
                )
            ):
                self.history.setItem(row, column, QTableWidgetItem(str(value or "")))


class ValidationPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Validation PM²")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        self.filter = QComboBox()
        self.filter.addItem("Toutes les sévérités", "")
        for value in ("ERROR", "WARNING", "INFO"):
            self.filter.addItem(value, value)
        self.filter.currentIndexChanged.connect(self.reload)
        heading.addWidget(self.filter)
        layout.addLayout(heading)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Sévérité", "Code", "Entité", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.reload()

    def reload(self) -> None:
        problems = ValidationService(self.session).validate_project(self.project.id)
        severity = self.filter.currentData()
        problems = [problem for problem in problems if not severity or problem.severity == severity]
        self.table.setRowCount(len(problems))
        colors = {
            "ERROR": QColor("#f8d7da"),
            "WARNING": QColor("#fff3cd"),
            "INFO": QColor("#dbeafe"),
        }
        for row, problem in enumerate(problems):
            for column, value in enumerate(
                (problem.severity, problem.code, problem.entity, problem.message)
            ):
                item = QTableWidgetItem(str(value))
                item.setBackground(colors[problem.severity])
                self.table.setItem(row, column, item)


class LifecyclePage(Page):
    def __init__(self, title: str, tabs: list[str], description: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        tab_widget = QTabWidget()
        for tab in tabs:
            tab_widget.addTab(InfoPanel(tab, description), tab)
        layout.addWidget(tab_widget)
