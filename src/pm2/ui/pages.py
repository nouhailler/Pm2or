from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.services import (
    AcceptanceService,
    DeliverableService,
    MeetingService,
    QualityService,
    RequirementService,
    TraceabilityService,
    TransitionService,
    WorkflowService,
    project_counts,
)
from pm2.application.validation import ValidationService
from pm2.infrastructure.orm import (
    AcceptanceCriterionModel,
    AcceptanceTestModel,
    DeliverableModel,
    ImplementationActivityModel,
    MeetingModel,
    ProjectModel,
    QualityControlModel,
    RequirementModel,
    TaskModel,
    TransitionActivityModel,
    WbsNodeModel,
)
from pm2.methodology.models import PM2Configuration
from pm2.ui.documents_page import DocumentsPage as DocumentsPage
from pm2.ui.gates_page import GatesPage as GatesPage
from pm2.ui.governance_page import GovernancePage as GovernancePage
from pm2.ui.info_panel import InfoPanel
from pm2.ui.page_base import Page as Page
from pm2.ui.project_workflow import ProjectWorkflow
from pm2.ui.registers_page import RegistersPage as RegistersPage
from pm2.ui.registers_page import RegisterTab as RegisterTab
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage
from pm2.ui.validation_page import ValidationPage as ValidationPage
from pm2.ui.work_plan_page import WorkPlanPage as WorkPlanPage


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
        self.actions_label = QLabel()
        self.actions_label.setWordWrap(True)
        actions_layout.addWidget(self.actions_label)
        root.addWidget(actions_group)
        root.addStretch()
        self.reload()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.dashboard_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.workflow.layout_route(watched.width())
        return super().eventFilter(watched, event)

    def reload(self) -> None:
        self.session.refresh(self.project)
        counts = project_counts(self.session, self.project.id)
        phase_names: dict[str, str] = {
            phase.code: phase.name for phase in self.workflow.phases
        }
        gate_names: dict[str, str] = {
            gate.from_phase: gate.name for gate in self.workflow.methodology.gates
        }
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
        self.actions_label.setText(
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

    def focus_section(self, key: str) -> None:
        keys = list(self.CONFIG)
        if key in keys:
            self.tabs.setCurrentIndex(keys.index(key))

    def _selected_entity(self) -> Any | None:
        key = self._current_key()
        table = self.tables[key]
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        entity_id = item.data(Qt.ItemDataRole.UserRole)
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
            task_targets = self.session.scalars(
                select(TaskModel)
                .join(WbsNodeModel)
                .where(WbsNodeModel.project_id == self.project.id)
            ).all()
            labels = [
                (f"{item.wbs_node.code} — {item.wbs_node.name}", item.id)
                for item in task_targets
            ]
        else:
            deliverable_targets = self.session.scalars(
                select(DeliverableModel).where(DeliverableModel.project_id == self.project.id)
            ).all()
            labels = [(f"{item.code} — {item.name}", item.id) for item in deliverable_targets]
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
