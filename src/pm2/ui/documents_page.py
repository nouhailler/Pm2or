from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.artifacts import ARTIFACT_SCHEMAS
from pm2.application.documents import DocumentService
from pm2.application.export import ExportService
from pm2.infrastructure.database import Database
from pm2.infrastructure.orm import (
    DocumentModel,
    DocumentVersionModel,
    ProjectModel,
)
from pm2.methodology.models import PM2Configuration
from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage


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
        item = self.table.item(row, 0) if row >= 0 else None
        return item.text() if item is not None else None

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
        item = self.table.item(row, 0)
        if item is None:
            return
        code = item.text()
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
            artifact_code = document.artifact_code
            if artifact_code is None:
                continue
            definition = self.methodology.artifacts[artifact_code]
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

