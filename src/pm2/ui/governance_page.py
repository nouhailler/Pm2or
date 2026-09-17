from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.services import (
    GovernanceService,
    ResponsibilityService,
)
from pm2.infrastructure.orm import (
    ProjectModel,
    ProjectRoleAssignmentModel,
    ResponsibilityAssignmentModel,
    RoleModel,
    StakeholderModel,
)
from pm2.methodology.models import PM2Configuration
from pm2.ui.info_panel import InfoPanel
from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage


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


