from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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

from pm2.application.resources import ResourceService
from pm2.infrastructure.orm import (
    PersonModel,
    ProjectModel,
    ResourceModel,
    TaskModel,
    TaskResourceAllocationModel,
    WbsNodeModel,
)
from pm2.ui.page_base import Page

RESOURCE_TYPE_LABELS = {
    "PERSON": "Personne",
    "TEAM": "Équipe",
    "SUPPLIER": "Fournisseur externe",
    "EQUIPMENT": "Équipement",
    "BUDGET": "Ressource budgétaire",
}


def _number(value: Decimal) -> str:
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


class ResourcesPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        layout = QVBoxLayout(self)
        title = QLabel("Gestion des ressources")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Capacité hebdomadaire, affectations aux tâches et détection des surcharges."
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_resources_tab()
        self._build_allocations_tab()
        self._build_capacity_tab()
        self.reload()

    def _build_resources_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        actions = QHBoxLayout()
        add_button = QPushButton("Ajouter une ressource")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_resource)
        availability_button = QPushButton("Définir une disponibilité")
        availability_button.clicked.connect(self._set_availability)
        archive_button = QPushButton("Archiver")
        archive_button.clicked.connect(self._archive_resource)
        actions.addWidget(add_button)
        actions.addWidget(availability_button)
        actions.addWidget(archive_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.resources = QTableWidget(0, 5)
        self.resources.setHorizontalHeaderLabels(
            ["Ressource", "Type", "Personne liée", "Disponibilité par défaut", "Description"]
        )
        self.resources.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.resources.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.resources)
        self.tabs.addTab(widget, "Ressources")

    def _build_allocations_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        actions = QHBoxLayout()
        add_button = QPushButton("Affecter à une tâche")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_allocation)
        remove_button = QPushButton("Retirer l'affectation")
        remove_button.clicked.connect(self._remove_allocation)
        actions.addWidget(add_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.allocations = QTableWidget(0, 5)
        self.allocations.setHorizontalHeaderLabels(
            ["Tâche", "Ressource", "Type", "Effort affecté", "Période"]
        )
        self.allocations.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.allocations.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.allocations)
        self.tabs.addTab(widget, "Affectations")

    def _build_capacity_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.capacity_summary = QLabel()
        self.capacity_summary.setWordWrap(True)
        layout.addWidget(self.capacity_summary)
        self.capacity = QTableWidget(0, 8)
        self.capacity.setHorizontalHeaderLabels(
            [
                "Ressource",
                "Type",
                "Semaine",
                "Disponibilité",
                "Capacité",
                "Charge",
                "Utilisation",
                "Charge visuelle",
            ]
        )
        self.capacity.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.capacity.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.capacity)
        self.tabs.addTab(widget, "Capacité hebdomadaire")

    def _add_resource(self) -> None:
        type_labels = [f"{code} — {label}" for code, label in RESOURCE_TYPE_LABELS.items()]
        selected_type, ok = QInputDialog.getItem(
            self, "Nouvelle ressource", "Type", type_labels, 0, False
        )
        if not ok:
            return
        resource_type = selected_type.split(" — ", 1)[0]
        person_id: str | None = None
        if resource_type == "PERSON":
            people = list(
                self.session.scalars(
                    select(PersonModel)
                    .where(PersonModel.archived.is_(False))
                    .order_by(PersonModel.name)
                ).all()
            )
            if not people:
                QMessageBox.information(
                    self,
                    "Ressource personne",
                    "Ajoutez d'abord la personne dans Gouvernance.",
                )
                return
            labels = [person.name for person in people]
            name, ok = QInputDialog.getItem(
                self, "Nouvelle ressource", "Personne", labels, 0, False
            )
            if not ok:
                return
            person = people[labels.index(name)]
            person_id = person.id
        else:
            name, ok = QInputDialog.getText(self, "Nouvelle ressource", "Nom")
            if not ok or not name.strip():
                return
        availability, ok = QInputDialog.getDouble(
            self, "Nouvelle ressource", "Disponibilité par défaut (%)", 100, 0, 100, 1
        )
        if not ok:
            return
        try:
            ResourceService(self.session).create(
                self.project.id,
                name,
                resource_type,
                person_id=person_id,
                default_availability_percent=Decimal(str(availability)),
            )
            self._commit_and_reload()
        except Exception as exc:
            self._show_error("Création impossible", exc)

    def _set_availability(self) -> None:
        resource = self._selected_resource()
        if resource is None:
            QMessageBox.information(self, "Disponibilité", "Sélectionnez une ressource.")
            return
        raw_week, ok = QInputDialog.getText(
            self,
            "Disponibilité hebdomadaire",
            "Lundi de la semaine (AAAA-MM-JJ)",
        )
        if not ok:
            return
        try:
            week_start = date.fromisoformat(raw_week.strip())
        except ValueError:
            QMessageBox.warning(self, "Date invalide", "Utilisez le format AAAA-MM-JJ.")
            return
        availability, ok = QInputDialog.getDouble(
            self, "Disponibilité hebdomadaire", "Disponibilité (%)", 100, 0, 100, 1
        )
        if not ok:
            return
        try:
            ResourceService(self.session).set_weekly_availability(
                resource.id, week_start, Decimal(str(availability))
            )
            self._commit_and_reload()
        except Exception as exc:
            self._show_error("Mise à jour impossible", exc)

    def _add_allocation(self) -> None:
        resources = self._active_resources()
        tasks = list(
            self.session.scalars(
                select(TaskModel)
                .join(WbsNodeModel)
                .where(
                    WbsNodeModel.project_id == self.project.id,
                    WbsNodeModel.archived.is_(False),
                    TaskModel.archived.is_(False),
                )
                .order_by(WbsNodeModel.code)
            ).all()
        )
        if not resources or not tasks:
            QMessageBox.information(
                self, "Affectation", "Créez au moins une ressource et une tâche."
            )
            return
        task_labels = [f"{task.wbs_node.code} — {task.wbs_node.name}" for task in tasks]
        task_label, ok = QInputDialog.getItem(
            self, "Affectation", "Tâche", task_labels, 0, False
        )
        if not ok:
            return
        resource_labels = [
            f"{resource.name} — {RESOURCE_TYPE_LABELS[resource.resource_type]}"
            for resource in resources
        ]
        resource_label, ok = QInputDialog.getItem(
            self, "Affectation", "Ressource", resource_labels, 0, False
        )
        if not ok:
            return
        effort, ok = QInputDialog.getDouble(
            self, "Affectation", "Effort affecté (jours)", 1, 0.01, 100_000, 2
        )
        if not ok:
            return
        try:
            ResourceService(self.session).allocate(
                tasks[task_labels.index(task_label)].id,
                resources[resource_labels.index(resource_label)].id,
                Decimal(str(effort)),
            )
            self._commit_and_reload()
        except Exception as exc:
            self._show_error("Affectation impossible", exc)

    def _remove_allocation(self) -> None:
        row = self.allocations.currentRow()
        item = self.allocations.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(self, "Affectation", "Sélectionnez une affectation.")
            return
        try:
            ResourceService(self.session).remove_allocation(
                item.data(Qt.ItemDataRole.UserRole)
            )
            self._commit_and_reload()
        except Exception as exc:
            self._show_error("Retrait impossible", exc)

    def _archive_resource(self) -> None:
        resource = self._selected_resource()
        if resource is None:
            QMessageBox.information(self, "Archivage", "Sélectionnez une ressource.")
            return
        answer = QMessageBox.question(
            self,
            "Archiver la ressource",
            f"Archiver {resource.name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            ResourceService(self.session).archive(resource.id)
            self._commit_and_reload()
        except Exception as exc:
            self._show_error("Archivage impossible", exc)

    def _selected_resource(self) -> ResourceModel | None:
        row = self.resources.currentRow()
        item = self.resources.item(row, 0) if row >= 0 else None
        return (
            self.session.get(ResourceModel, item.data(Qt.ItemDataRole.UserRole))
            if item is not None
            else None
        )

    def _active_resources(self) -> list[ResourceModel]:
        return list(
            self.session.scalars(
                select(ResourceModel)
                .where(
                    ResourceModel.project_id == self.project.id,
                    ResourceModel.archived.is_(False),
                )
                .order_by(ResourceModel.name)
            ).all()
        )

    def _commit_and_reload(self) -> None:
        self.session.commit()
        self.reload()
        self.changed.emit()

    def _show_error(self, title: str, error: Exception) -> None:
        self.session.rollback()
        QMessageBox.critical(self, title, str(error))

    def reload(self) -> None:
        resources = self._active_resources()
        self.resources.setRowCount(len(resources))
        for row, resource in enumerate(resources):
            values = (
                resource.name,
                RESOURCE_TYPE_LABELS[resource.resource_type],
                resource.person.name if resource.person else "—",
                f"{resource.default_availability_percent} %",
                resource.description,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, resource.id)
                self.resources.setItem(row, column, item)

        resource_ids = [resource.id for resource in resources]
        allocations = (
            list(
                self.session.scalars(
                    select(TaskResourceAllocationModel)
                    .join(TaskModel)
                    .join(WbsNodeModel)
                    .where(
                        WbsNodeModel.project_id == self.project.id,
                        TaskResourceAllocationModel.resource_id.in_(resource_ids),
                    )
                    .order_by(WbsNodeModel.code)
                ).all()
            )
            if resource_ids
            else []
        )
        self.allocations.setRowCount(len(allocations))
        for row, allocation in enumerate(allocations):
            task = allocation.task
            resource = allocation.resource
            period = f"{task.planned_start or '—'} → {task.planned_end or '—'}"
            values = (
                f"{task.wbs_node.code} — {task.wbs_node.name}",
                resource.name,
                RESOURCE_TYPE_LABELS[resource.resource_type],
                f"{_number(allocation.effort_days)} j",
                period,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, allocation.id)
                self.allocations.setItem(row, column, item)

        utilization = ResourceService(self.session).utilization(self.project.id)
        overloaded = sum(item.overloaded for item in utilization)
        self.capacity_summary.setText(
            f"{overloaded} surcharge(s) détectée(s). "
            "La capacité hebdomadaire standard correspond à 5 jours à 100 %."
        )
        self.capacity.setRowCount(len(utilization))
        for row, load in enumerate(utilization):
            percent = load.utilization_percent
            percent_label = "∞" if percent is None and load.allocated_days > 0 else (
                f"{percent} %" if percent is not None else "—"
            )
            blocks = 0 if percent is None else min(12, max(0, round(float(percent) / 10)))
            bar = "█" * blocks + "░" * (10 - min(blocks, 10))
            if load.overloaded:
                bar += " ⚠"
            capacity_values = (
                load.resource_name,
                RESOURCE_TYPE_LABELS[load.resource_type],
                f"{load.week_start.isocalendar().year}-S{load.week_start.isocalendar().week:02d}",
                f"{load.availability_percent} %",
                f"{load.capacity_days} j",
                f"{load.allocated_days} j",
                percent_label,
                bar,
            )
            for column, value in enumerate(capacity_values):
                item = QTableWidgetItem(str(value))
                if load.overloaded:
                    item.setBackground(QColor("#ffe4e0"))
                    item.setForeground(QColor("#8c1d18"))
                self.capacity.setItem(row, column, item)
