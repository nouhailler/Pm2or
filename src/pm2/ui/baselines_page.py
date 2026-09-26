from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy.orm import Session

from pm2.application.baselines import BaselineComparison, BaselineService
from pm2.infrastructure.orm import BaselineModel, ProjectModel
from pm2.ui.page_base import Page


class BaselinesPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session = session
        self.project = project
        self.service = BaselineService(session)
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Baselines immuables")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Figer une référence approuvée, puis mesurer les écarts avec l’état courant."
        )
        subtitle.setObjectName("pageSubtitle")
        title_box = QVBoxLayout()
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box)
        heading.addStretch()
        create = QPushButton("Créer une baseline")
        create.setObjectName("primaryButton")
        create.clicked.connect(self._create)
        approve = QPushButton("Approuver")
        approve.clicked.connect(self._approve)
        compare = QPushButton("Comparer à l’état actuel")
        compare.clicked.connect(self._compare)
        heading.addWidget(create)
        heading.addWidget(approve)
        heading.addWidget(compare)
        layout.addLayout(heading)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Référence", "Nom", "Type", "Créée le", "Créée par", "Approbation", "SHA-256"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setProperty("pm2CustomRowDetail", True)
        header = self.table.horizontalHeader()
        for column in (0, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.reload()

    def _selected(self) -> BaselineModel | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        baseline_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return self.service.require(str(baseline_id)) if baseline_id else None

    def _create(self) -> None:
        name, ok = QInputDialog.getText(self, "Nouvelle baseline", "Nom de la référence :")
        if not ok:
            return
        baseline_type, ok = QInputDialog.getItem(
            self,
            "Nouvelle baseline",
            "Type :",
            ["PROJECT", "PLANNING", "SCOPE", "COST", "DOCUMENTS"],
            editable=True,
        )
        if not ok:
            return
        created_by, ok = QInputDialog.getText(self, "Nouvelle baseline", "Créée par :")
        if not ok:
            return
        try:
            baseline = self.service.create(
                self.project.id,
                name=name,
                baseline_type=baseline_type,
                created_by=created_by,
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
            QMessageBox.information(
                self,
                "Baseline créée",
                f"{baseline.code} a été figée. Son snapshot et son empreinte sont immuables.",
            )
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Création impossible", str(exc))

    def _approve(self) -> None:
        baseline = self._selected()
        if baseline is None:
            QMessageBox.information(self, "Approbation", "Sélectionnez une baseline.")
            return
        if baseline.approved_at is not None:
            QMessageBox.information(
                self, "Approbation", f"{baseline.code} est déjà approuvée par {baseline.approved_by}."
            )
            return
        approved_by, ok = QInputDialog.getText(self, "Approbation", "Approuvée par :")
        if not ok:
            return
        try:
            self.service.approve(baseline.id, approved_by=approved_by)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Approbation impossible", str(exc))

    def _compare(self) -> None:
        baseline = self._selected()
        if baseline is None:
            QMessageBox.information(self, "Comparaison", "Sélectionnez une baseline.")
            return
        try:
            comparison = self.service.compare(baseline.id)
            self._show_comparison(comparison)
        except Exception as exc:
            QMessageBox.critical(self, "Comparaison impossible", str(exc))

    def _show_comparison(self, comparison: BaselineComparison) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Écarts — {comparison.baseline.code}")
        dialog.resize(1100, 720)
        layout = QVBoxLayout(dialog)
        summary = QLabel(
            f"{len(comparison.differences)} écart(s) : "
            f"{comparison.added} ajout(s), {comparison.removed} retrait(s), "
            f"{comparison.changed} modification(s)."
        )
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(self._comparison_text(comparison))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(summary)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        dialog.exec()

    @staticmethod
    def _comparison_text(comparison: BaselineComparison) -> str:
        if not comparison.differences:
            return "Aucun écart : l’état actuel correspond à la baseline."

        def display(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

        return "\n\n".join(
            f"[{item.change}] {item.path}\n"
            f"  Baseline : {display(item.baseline)}\n"
            f"  Actuel   : {display(item.current)}"
            for item in comparison.differences
        )

    def reload(self) -> None:
        current = self._selected() if self.table.currentRow() >= 0 else None
        selected = current.id if current is not None else None
        baselines = self.service.list(self.project.id)
        self.table.setRowCount(len(baselines))
        selected_row = -1
        for row, baseline in enumerate(baselines):
            code = QTableWidgetItem(baseline.code)
            code.setData(Qt.ItemDataRole.UserRole, baseline.id)
            approval = (
                f"{baseline.approved_at:%d.%m.%Y} · {baseline.approved_by}"
                if baseline.approved_at
                else "En attente"
            )
            values = [
                code,
                QTableWidgetItem(baseline.name),
                QTableWidgetItem(baseline.type),
                QTableWidgetItem(baseline.created_at.strftime("%d.%m.%Y %H:%M")),
                QTableWidgetItem(baseline.created_by),
                QTableWidgetItem(approval),
                QTableWidgetItem(baseline.hash),
            ]
            for column, item in enumerate(values):
                self.table.setItem(row, column, item)
            if baseline.id == selected:
                selected_row = row
        if selected_row >= 0:
            self.table.selectRow(selected_row)
