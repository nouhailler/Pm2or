from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.traceability import TraceabilityService
from pm2.infrastructure.orm import ProjectModel, TraceLinkModel
from pm2.ui.dialogs import TraceLinkDialog
from pm2.ui.page_base import Page


class TraceabilityPage(Page):
    """Project traceability screen, isolated from the general page catalogue."""

    changed = Signal()
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
