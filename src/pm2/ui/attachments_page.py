from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy.orm import Session

from pm2.application.attachments import AttachmentService
from pm2.infrastructure.orm import ProjectModel
from pm2.ui.page_base import Page


class AttachmentsPage(Page):
    def __init__(self, session: Session, project: ProjectModel, cache_dir: Path) -> None:
        super().__init__()
        self.session = session
        self.project = project
        self.cache_dir = cache_dir
        self.service = AttachmentService(session)
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Pièces jointes")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        add = QPushButton("Ajouter…")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        open_button = QPushButton("Ouvrir")
        open_button.clicked.connect(self._open)
        remove = QPushButton("Supprimer")
        remove.clicked.connect(self._remove)
        heading.addWidget(add)
        heading.addWidget(open_button)
        heading.addWidget(remove)
        layout.addLayout(heading)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Nom", "Type", "Taille", "Description", "SHA-256"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(lambda _item: self._open())
        layout.addWidget(self.table)
        self.reload()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _add(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Ajouter une pièce jointe")
        if not filename:
            return
        description, accepted = QInputDialog.getText(
            self, "Description", "Description ou référence de la pièce :"
        )
        if not accepted:
            return
        try:
            self.service.add(self.project.id, Path(filename), description)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Ajout impossible", str(exc))

    def _open(self) -> None:
        attachment_id = self._selected_id()
        if attachment_id is None:
            QMessageBox.information(self, "Pièce jointe", "Sélectionnez un fichier.")
            return
        try:
            path = self.service.materialize(self.project.id, attachment_id, self.cache_dir)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
                raise OSError("Aucune application ne peut ouvrir ce type de fichier.")
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))

    def _remove(self) -> None:
        attachment_id = self._selected_id()
        if attachment_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Supprimer la pièce jointe",
            "Retirer cette pièce du projet ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.remove(self.project.id, attachment_id)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Suppression impossible", str(exc))

    def reload(self) -> None:
        attachments = self.service.list(self.project.id)
        self.table.setRowCount(len(attachments))
        for row, attachment in enumerate(attachments):
            values = (
                attachment.filename,
                attachment.media_type,
                f"{attachment.size_bytes / 1024:.1f} Kio",
                attachment.description,
                attachment.content_hash,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, attachment.id)
                self.table.setItem(row, column, item)
