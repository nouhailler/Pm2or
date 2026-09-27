from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pm2.application.audit import AuditTrailService
from pm2.infrastructure.orm import AuditEventModel, ProjectModel
from pm2.ui.page_base import Page


class AuditTrailPage(Page):
    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session = session
        self.project = project
        self.service = AuditTrailService(session)
        root = QVBoxLayout(self)
        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Audit Trail")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Chronologie complète des actions, utilisateurs et valeurs Avant/Après.")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box)
        heading.addStretch()
        export = QPushButton("Exporter le journal JSON")
        export.clicked.connect(self._export)
        heading.addWidget(export)
        root.addLayout(heading)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un objet, une action ou une raison…")
        self.entity_filter = QComboBox()
        self.actor_filter = QComboBox()
        refresh = QPushButton("Actualiser")
        filters.addWidget(self.search, 2)
        filters.addWidget(self.entity_filter)
        filters.addWidget(self.actor_filter)
        filters.addWidget(refresh)
        root.addLayout(filters)
        self.search.textChanged.connect(self.reload)
        self.entity_filter.currentIndexChanged.connect(self.reload)
        self.actor_filter.currentIndexChanged.connect(self.reload)
        refresh.clicked.connect(self.reload)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.timeline = QTreeWidget()
        self.timeline.setColumnCount(4)
        self.timeline.setHeaderLabels(["Date", "Événement", "Utilisateur", "Origine"])
        self.timeline.setRootIsDecorated(True)
        self.timeline.setAlternatingRowColors(True)
        self.timeline.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.timeline.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.timeline.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.timeline.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.timeline.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.timeline.currentItemChanged.connect(self._show_event)
        splitter.addWidget(self.timeline)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.event_title = QLabel("Sélectionnez un événement dans la timeline.")
        self.event_title.setObjectName("sectionTitle")
        self.event_metadata = QLabel()
        self.event_metadata.setWordWrap(True)
        self.event_reason = QLabel()
        self.event_reason.setWordWrap(True)
        self.event_reason.setObjectName("pageSubtitle")
        detail_layout.addWidget(self.event_title)
        detail_layout.addWidget(self.event_metadata)
        detail_layout.addWidget(self.event_reason)
        self.changes = QTableWidget(0, 3)
        self.changes.setHorizontalHeaderLabels(["Champ", "Avant", "Après"])
        self.changes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.changes.setProperty("pm2CustomRowDetail", True)
        self.changes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.changes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.changes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        detail_layout.addWidget(self.changes, 2)
        raw = QTabWidget()
        self.before = QPlainTextEdit()
        self.after = QPlainTextEdit()
        for editor in (self.before, self.after):
            editor.setReadOnly(True)
        raw.addTab(self.before, "Avant")
        raw.addTab(self.after, "Après")
        detail_layout.addWidget(raw, 1)
        splitter.addWidget(detail)
        splitter.setSizes([620, 650])
        root.addWidget(splitter, 1)
        self._reload_filters()
        self.reload()

    def _reload_filters(self) -> None:
        current_type = self.entity_filter.currentData()
        current_actor = self.actor_filter.currentData()
        self.entity_filter.blockSignals(True)
        self.actor_filter.blockSignals(True)
        self.entity_filter.clear()
        self.actor_filter.clear()
        self.entity_filter.addItem("Tous les objets", None)
        self.actor_filter.addItem("Tous les utilisateurs", None)
        for value in self.service.entity_types(self.project.id):
            self.entity_filter.addItem(value, value)
        for value in self.service.actors(self.project.id):
            self.actor_filter.addItem(value, value)
        type_index = self.entity_filter.findData(current_type)
        actor_index = self.actor_filter.findData(current_actor)
        self.entity_filter.setCurrentIndex(max(0, type_index))
        self.actor_filter.setCurrentIndex(max(0, actor_index))
        self.entity_filter.blockSignals(False)
        self.actor_filter.blockSignals(False)

    @staticmethod
    def _action_text(event: AuditEventModel) -> str:
        if event.action.startswith("TRANSITION:"):
            transition = event.action.removeprefix("TRANSITION:")
            return f"statut {transition}"
        labels = {
            "CREATE": "créé",
            "UPDATE": "modifié",
            "APPROVE": "approuvé",
            "ARCHIVE": "archivé",
            "RESTORE": "restauré",
            "DELETE": "supprimé",
            "ACCEPTED": "accepté",
            "METHODOLOGY_UPGRADE": "méthodologie mise à niveau",
        }
        return labels.get(event.action, event.action.replace("_", " ").lower())

    def reload(self) -> None:
        selected = self._selected_event_id()
        events = self.service.list(
            self.project.id,
            entity_type=self.entity_filter.currentData(),
            actor=self.actor_filter.currentData(),
            search=self.search.text(),
        )
        self.timeline.clear()
        selected_item: QTreeWidgetItem | None = None
        for event in events:
            item = QTreeWidgetItem(
                [
                    event.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                    f"{event.object_label} — {self._action_text(event)}",
                    event.actor,
                    event.origin,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, event.id)
            item.setToolTip(1, event.reason or "Aucune raison renseignée")
            self.timeline.addTopLevelItem(item)
            if event.id == selected:
                selected_item = item
        if selected_item is not None:
            self.timeline.setCurrentItem(selected_item)
        elif self.timeline.topLevelItemCount():
            first_item = self.timeline.topLevelItem(0)
            if first_item is not None:
                self.timeline.setCurrentItem(first_item)
        else:
            self._clear_detail()

    def _selected_event_id(self) -> str | None:
        item = self.timeline.currentItem()
        value = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        return str(value) if value else None

    def _show_event(
        self, item: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if item is None:
            self._clear_detail()
            return
        event_id = item.data(0, Qt.ItemDataRole.UserRole)
        event = self.session.get(AuditEventModel, event_id)
        if event is None:
            self._clear_detail()
            return
        self.event_title.setText(f"{event.object_label} — {self._action_text(event)}")
        self.event_metadata.setText(
            f"{event.timestamp:%d.%m.%Y %H:%M:%S} · Utilisateur : {event.actor} · "
            f"Origine : {event.origin} · Objet : {event.entity_type}/{event.entity_id}"
        )
        self.event_reason.setText(f"Raison : {event.reason or 'Non renseignée'}")
        changes = self.service.changes(event)
        self.changes.setRowCount(len(changes))
        for row, change in enumerate(changes):
            for column, value in enumerate(
                (change.field, self._display(change.before), self._display(change.after))
            ):
                self.changes.setItem(row, column, QTableWidgetItem(value))
        before, after = self.service.values(event)
        self.before.setPlainText(self._display(before, pretty=True))
        self.after.setPlainText(self._display(after, pretty=True))

    @staticmethod
    def _display(value: Any, *, pretty: bool = False) -> str:
        if value is None:
            return "—"
        if isinstance(value, (dict, list)):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                indent=2 if pretty else None,
                default=str,
            )
        return str(value)

    def _clear_detail(self) -> None:
        self.event_title.setText("Aucun événement")
        self.event_metadata.clear()
        self.event_reason.clear()
        self.changes.setRowCount(0)
        self.before.clear()
        self.after.clear()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter l’Audit Trail",
            f"{self.project.reference}-audit.json",
            "Journal JSON (*.json)",
        )
        if not path:
            return
        try:
            destination = self.service.export_json(self.project.id, Path(path).with_suffix(".json"))
            QMessageBox.information(self, "Audit exporté", f"Journal créé :\n{destination}")
        except OSError as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))
