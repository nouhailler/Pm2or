from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.services import (
    WorkPlanService,
)
from pm2.infrastructure.orm import (
    ProjectModel,
    TaskDependencyModel,
    TaskModel,
    WbsNodeModel,
)
from pm2.ui.dialogs import WbsNodeDialog
from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage


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
        dependency_item = self.dependencies.item(row, 0)
        if dependency_item is None:
            return
        dependency_id = dependency_item.data(Qt.ItemDataRole.UserRole)
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
            tree_item = QTreeWidgetItem(
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
            tree_item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            items[node.id] = tree_item
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
            gantt_values = (
                f"{node.code} — {node.name}",
                str(task.planned_start or ""),
                str(task.planned_end or ""),
                f"{duration} j",
                "█" * min(duration, 40),
            )
            for column, value in enumerate(gantt_values):
                table_item = QTableWidgetItem(value)
                if column == 4:
                    table_item.setForeground(QColor("#2f6b91"))
                self.gantt.setItem(row, column, table_item)
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
            dependency_values = (
                f"{predecessor.code} — {predecessor.name}",
                dependency.dependency_type,
                f"{successor.code} — {successor.name}",
                f"{dependency.lag_days} j",
            )
            for column, value in enumerate(dependency_values):
                dependency_table_item = QTableWidgetItem(value)
                if column == 0:
                    dependency_table_item.setData(Qt.ItemDataRole.UserRole, dependency.id)
                self.dependencies.setItem(row, column, dependency_table_item)
        if select_id and select_id in items:
            self.tree.setCurrentItem(items[select_id])

