from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
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

from pm2.application.crud import EntityCrudService
from pm2.application.services import (
    RegisterService,
    WorkflowService,
)
from pm2.infrastructure.orm import (
    ChangeModel,
    DecisionModel,
    IssueModel,
    ProjectModel,
    RiskModel,
)
from pm2.ui.crud import FIELD_LABELS, EntityCatalogPage, EntityEditDialog
from pm2.ui.dialogs import RegisterItemDialog
from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage

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
        item = self.table.item(row, 0)
        if item is None:
            return None
        entity_id = item.data(Qt.ItemDataRole.UserRole)
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
            item = catalog.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == entity.id:
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

    def focus_section(self, kind: str) -> None:
        kinds = ("risk", "issue", "decision", "change")
        if kind in kinds:
            self.tabs.setCurrentIndex(kinds.index(kind))
