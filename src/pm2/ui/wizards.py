from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.artifacts import ARTIFACT_SCHEMAS, ArtifactDataService
from pm2.application.documents import DocumentService
from pm2.application.services import GateService, ProjectService, WorkflowService, project_counts
from pm2.application.validation import ValidationService
from pm2.domain.enums import GateDecisionType
from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE
from pm2.infrastructure.orm import DocumentModel, ProjectModel
from pm2.methodology.models import PM2Configuration
from pm2.ui.acceptance import AcceptanceExecutionWidget

PHASE_ARTIFACTS = {
    "LAUNCH": (
        "PROJECT_INITIATION_REQUEST",
        "BUSINESS_CASE",
        "PROJECT_CHARTER",
    ),
    "PLANNING": (
        "PROJECT_HANDBOOK",
        "STAKEHOLDER_MATRIX",
        "WORK_PLAN",
        "OUTSOURCING_PLAN",
        "DELIVERABLE_ACCEPTANCE_PLAN",
        "TRANSITION_PLAN",
        "ORGANISATIONAL_IMPLEMENTATION_PLAN",
        "REQUIREMENTS_MANAGEMENT_PLAN",
        "CHANGE_MANAGEMENT_PLAN",
        "RISK_MANAGEMENT_PLAN",
        "ISSUE_MANAGEMENT_PLAN",
        "QUALITY_MANAGEMENT_PLAN",
        "COMMUNICATIONS_MANAGEMENT_PLAN",
    ),
    "EXECUTION": ("MEETING_MINUTES", "PROJECT_REPORT", "QUALITY_REPORT"),
    "CLOSING": ("PROJECT_END_REPORT", "LESSONS_LEARNED"),
}

class ArtifactEditor(QWidget):
    changed = Signal()

    def __init__(
        self,
        session: Session,
        project: ProjectModel,
        methodology: PM2Configuration,
        artifact_code: str,
    ) -> None:
        super().__init__()
        self.session, self.project = session, project
        self.methodology, self.artifact_code = methodology, artifact_code
        self.data_service = ArtifactDataService(session)
        self.schema = ARTIFACT_SCHEMAS[artifact_code]
        self.fields: dict[str, QPlainTextEdit] = {}
        root = QVBoxLayout(self)
        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(self.schema.title)
        title.setObjectName("sectionTitle")
        purpose = QLabel(self.schema.purpose)
        purpose.setObjectName("pageSubtitle")
        purpose.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(purpose)
        heading.addLayout(title_box, 1)
        self.status_label = QLabel()
        heading.addWidget(self.status_label)
        root.addLayout(heading)
        completion_layout = QHBoxLayout()
        completion_layout.addWidget(QLabel("Complétude"))
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        completion_layout.addWidget(self.progress, 1)
        root.addLayout(completion_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for section in self.schema.sections:
            group = QGroupBox(section.title)
            form = QFormLayout(group)
            for definition in section.fields:
                editor = QPlainTextEdit()
                editor.setMaximumHeight(82)
                editor.setPlaceholderText(definition.help_text or definition.label)
                editor.textChanged.connect(self._update_completion_preview)
                self.fields[definition.code] = editor
                form.addRow(definition.label + (" *" if definition.required else ""), editor)
            content_layout.addWidget(group)
        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.missing = QLabel()
        self.missing.setWordWrap(True)
        root.addWidget(self.missing)
        buttons = QHBoxLayout()
        save = QPushButton("Enregistrer")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save)
        self.transition = QPushButton("Faire avancer le document")
        self.transition.clicked.connect(self.advance_document)
        buttons.addStretch()
        buttons.addWidget(save)
        buttons.addWidget(self.transition)
        root.addLayout(buttons)
        self.reload()

    def values(self) -> dict[str, str]:
        return {code: editor.toPlainText().strip() for code, editor in self.fields.items()}

    def save(self) -> None:
        try:
            self.data_service.save(self.project.id, self.artifact_code, self.values())
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))

    def advance_document(self) -> None:
        document = self._document()
        targets = sorted(DEFAULT_WORKFLOW_ENGINE.allowed_targets("document", document.status))
        if not targets:
            QMessageBox.information(self, "Workflow documentaire", "Aucune transition disponible.")
            return
        target, ok = QInputDialogCompat.item(
            self, "Workflow documentaire", f"Statut actuel : {document.status}", targets
        )
        if not ok:
            return
        if target in {"APPROVED", "BASELINED"} and self.preview_completion() < 100:
            QMessageBox.warning(
                self,
                "Document incomplet",
                "Tous les champs obligatoires doivent être renseignés avant approbation.",
            )
            return
        try:
            WorkflowService(self.session).transition("document", document.id, target)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Transition refusée", str(exc))

    def preview_completion(self) -> int:
        required = [
            definition
            for section in self.schema.sections
            for definition in section.fields
            if definition.required
        ]
        if not required:
            return 100
        filled = sum(bool(self.fields[item.code].toPlainText().strip()) for item in required)
        return round(filled * 100 / len(required))

    def _update_completion_preview(self) -> None:
        completion = self.preview_completion()
        self.progress.setValue(completion)
        missing = [
            item.label
            for section in self.schema.sections
            for item in section.fields
            if item.required and not self.fields[item.code].toPlainText().strip()
        ]
        self.missing.setText(
            "Champs requis manquants : " + ", ".join(missing)
            if missing
            else "Tous les champs requis sont renseignés."
        )

    def reload(self) -> None:
        values = self.data_service.load(self.project.id, self.artifact_code)
        for code, editor in self.fields.items():
            editor.blockSignals(True)
            editor.setPlainText(values.get(code, ""))
            editor.blockSignals(False)
        document = self._document()
        self.status_label.setText(f"{self.artifact_code}\nStatut : {document.status}")
        self._update_completion_preview()

    def _document(self) -> DocumentModel:
        document = self.session.scalar(
            select(DocumentModel).where(
                DocumentModel.project_id == self.project.id,
                DocumentModel.artifact_code == self.artifact_code,
            )
        )
        if document is None:
            DocumentService(self.session, self.methodology).ensure_catalog(self.project.id)
            document = self.session.scalar(
                select(DocumentModel).where(
                    DocumentModel.project_id == self.project.id,
                    DocumentModel.artifact_code == self.artifact_code,
                )
            )
        assert document is not None
        return document


class QInputDialogCompat:
    """Petit dialogue non éditable, facilement pilotable par pytest-qt."""

    @staticmethod
    def item(parent: QWidget, title: str, label: str, values: list[str]) -> tuple[str, bool]:
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(label))
        combo = QComboBox()
        combo.addItems(values)
        combo.setObjectName("choice")
        layout.addWidget(combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return combo.currentText(), accepted


class GateAssistant(QWidget):
    changed = Signal()

    def __init__(
        self,
        session: Session,
        project: ProjectModel,
        methodology: PM2Configuration,
        gate_code: str,
    ) -> None:
        super().__init__()
        self.session, self.project, self.methodology = session, project, methodology
        self.gate_code = gate_code
        self.service = GateService(session, methodology)
        self.review = self.service.get_or_create(project.id, gate_code)
        definition = methodology.gate(gate_code)
        root = QVBoxLayout(self)
        title = QLabel(f"{definition.name} — {definition.label}")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        self.summary = QLabel()
        root.addWidget(self.summary)
        checklist = QGroupBox("Checklist et preuves")
        checklist_layout = QVBoxLayout(checklist)
        self.items: list[tuple[QCheckBox, QLineEdit, str]] = []
        for item in self.service.checklist(self.review.id):
            row = QHBoxLayout()
            checkbox = QCheckBox(
                f"{item.item_code} — {item.description}" + (" *" if item.required else "")
            )
            checkbox.setChecked(item.satisfied)
            evidence = QLineEdit(item.evidence)
            evidence.setPlaceholderText("Preuve / commentaire")
            row.addWidget(checkbox, 2)
            row.addWidget(evidence, 1)
            checklist_layout.addLayout(row)
            self.items.append((checkbox, evidence, item.id))
        root.addWidget(checklist)
        decision_group = QGroupBox("Décision")
        form = QFormLayout(decision_group)
        self.decision = QComboBox()
        self.decision.addItems([item.value for item in GateDecisionType])
        self.decider = QLineEdit()
        self.comments = QPlainTextEdit()
        self.comments.setMaximumHeight(90)
        form.addRow("Décision", self.decision)
        form.addRow("Décideur *", self.decider)
        form.addRow("Commentaires / réserves", self.comments)
        root.addWidget(decision_group)
        buttons = QHBoxLayout()
        save_checklist = QPushButton("Enregistrer la checklist")
        save_checklist.clicked.connect(self.save_checklist)
        decide = QPushButton("Enregistrer la décision")
        decide.setObjectName("primaryButton")
        decide.clicked.connect(self.save_decision)
        buttons.addStretch()
        buttons.addWidget(save_checklist)
        buttons.addWidget(decide)
        root.addLayout(buttons)
        root.addStretch()
        self.session.commit()
        self.reload()

    def save_checklist(self) -> None:
        try:
            for checkbox, evidence, item_id in self.items:
                self.service.set_item(item_id, checkbox.isChecked(), evidence.text().strip())
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Checklist invalide", str(exc))

    def save_decision(self) -> None:
        if not self.decider.text().strip():
            QMessageBox.warning(self, "Décideur requis", "Indiquez le décideur.")
            return
        try:
            self.save_checklist()
            self.service.decide(
                self.review.id,
                self.decision.currentText(),
                self.decider.text().strip(),
                self.comments.toPlainText().strip(),
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Décision refusée", str(exc))

    def reload(self) -> None:
        self.session.refresh(self.project)
        self.session.refresh(self.review)
        for checkbox, evidence, item_id in self.items:
            item = next(
                value for value in self.service.checklist(self.review.id) if value.id == item_id
            )
            checkbox.blockSignals(True)
            checkbox.setChecked(item.satisfied)
            checkbox.blockSignals(False)
            evidence.setText(item.evidence)
        self.summary.setText(
            f"Phase actuelle : {self.project.current_phase} · Cible : {self.review.to_phase} · "
            f"Statut : {self.review.status}"
        )


class PhaseOverview(QWidget):
    def __init__(self, session: Session, project: ProjectModel, phase: str) -> None:
        super().__init__()
        self.session, self.project, self.phase = session, project, phase
        layout = QVBoxLayout(self)
        title = QLabel(f"Vue d’ensemble — {phase}")
        title.setObjectName("sectionTitle")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.summary)
        layout.addStretch()
        self.reload()

    def reload(self) -> None:
        counts = project_counts(self.session, self.project.id)
        self.summary.setText(
            f"Phase actuelle : {self.project.current_phase}\n\n"
            f"Avancement moyen : {counts['progress']} %\n"
            f"Livrables : {counts['deliverables']} · Exigences : {counts['requirements']}\n"
            f"Risques ouverts : {counts['risks']} · Problèmes ouverts : {counts['issues']} · "
            f"Modifications : {counts['changes']}\n\n"
            "Les onglets suivants enregistrent les données structurées, calculent leur complétude "
            "et pilotent le statut documentaire."
        )


class AdministrativeClosure(QWidget):
    changed = Signal()

    def __init__(
        self, session: Session, project: ProjectModel, methodology: PM2Configuration
    ) -> None:
        super().__init__()
        self.session, self.project, self.methodology = session, project, methodology
        layout = QVBoxLayout(self)
        title = QLabel("Fermeture administrative")
        title.setObjectName("sectionTitle")
        self.status = QLabel()
        self.confirm = QCheckBox(
            "Je confirme que les acceptations, transferts, archives et actions résiduelles sont traités."
        )
        close = QPushButton("Fermer définitivement le projet")
        close.setObjectName("primaryButton")
        close.clicked.connect(self.close_project)
        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addWidget(self.confirm)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        self.reload()

    def close_project(self) -> None:
        if not self.confirm.isChecked():
            QMessageBox.warning(
                self, "Confirmation requise", "Confirmez les opérations administratives."
            )
            return
        try:
            ProjectService(self.session, self.methodology).close(self.project.id)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Fermeture refusée", str(exc))

    def reload(self) -> None:
        self.session.refresh(self.project)
        self.status.setText(
            f"Projet : {self.project.reference} · Phase : {self.project.current_phase} · "
            f"Statut : {self.project.status}"
        )


class PhaseAssistantPage(QWidget):
    changed = Signal()
    navigate_requested = Signal(str)

    def __init__(
        self,
        session: Session,
        project: ProjectModel,
        methodology: PM2Configuration,
        phase: str,
    ) -> None:
        super().__init__()
        self.session, self.project, self.methodology, self.phase = (
            session,
            project,
            methodology,
            phase,
        )
        self.editors: list[ArtifactEditor] = []
        root = QVBoxLayout(self)
        heading = QHBoxLayout()
        names = {
            "LAUNCH": "Assistant de Lancement",
            "PLANNING": "Assistant de Planification",
            "EXECUTION": "Assistant d’Exécution",
            "CLOSING": "Assistant de Clôture",
        }
        title = QLabel(names[phase])
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        self.completion = QProgressBar()
        self.completion.setFixedWidth(260)
        heading.addWidget(self.completion)
        root.addLayout(heading)
        source_bar = QHBoxLayout()
        source_bar.addWidget(QLabel("Données sources :"))
        destinations = {
            "LAUNCH": (("Projet", "Projet"), ("Gouvernance", "Gouvernance")),
            "PLANNING": (
                ("Gouvernance", "Gouvernance"),
                ("WBS / Gantt", "Plan de travail"),
                ("Besoins et livrables", "Données métier"),
                ("Registres", "Registres"),
            ),
            "EXECUTION": (
                ("Tâches", "Plan de travail"),
                ("Livrables / qualité / réunions", "Données métier"),
                ("Registres", "Registres"),
            ),
            "CLOSING": (
                ("Acceptations", "Données métier"),
                ("Actions résiduelles", "Registres"),
                ("Documents", "Documents"),
            ),
        }
        for label, destination in destinations[phase]:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, value=destination: self.navigate_requested.emit(value)
            )
            source_bar.addWidget(button)
        source_bar.addStretch()
        root.addLayout(source_bar)
        self.validation_summary = QLabel()
        self.validation_summary.setWordWrap(True)
        self.validation_summary.setObjectName("pageSubtitle")
        root.addWidget(self.validation_summary)
        self.tabs = QTabWidget()
        self.overview = PhaseOverview(session, project, phase)
        self.tabs.addTab(self.overview, "Vue d’ensemble")
        DocumentService(session, methodology).ensure_catalog(project.id)
        for artifact_code in PHASE_ARTIFACTS[phase]:
            editor = ArtifactEditor(session, project, methodology, artifact_code)
            editor.changed.connect(self._child_changed)
            self.editors.append(editor)
            self.tabs.addTab(editor, ARTIFACT_SCHEMAS[artifact_code].title)
        if phase in {"EXECUTION", "CLOSING"}:
            acceptance = AcceptanceExecutionWidget(session, project)
            acceptance.changed.connect(self._child_changed)
            self.tabs.addTab(acceptance, "Acceptation finale")
            self.acceptance = acceptance
        else:
            self.acceptance = None
        gate_code = next((gate.code for gate in methodology.gates if gate.from_phase == phase), None)
        if gate_code:
            gate = GateAssistant(session, project, methodology, gate_code)
            gate.changed.connect(self._child_changed)
            self.gate = gate
            self.tabs.addTab(gate, methodology.gate(gate_code).name)
        else:
            self.gate = None
        if phase == "CLOSING":
            closing = AdministrativeClosure(session, project, methodology)
            closing.changed.connect(self._child_changed)
            self.tabs.addTab(closing, "Fermeture administrative")
            self.closing = closing
        else:
            self.closing = None
        self.session.commit()
        root.addWidget(self.tabs)
        self.reload()

    def _child_changed(self) -> None:
        self.reload()
        self.changed.emit()

    def reload(self) -> None:
        service = ArtifactDataService(self.session)
        values = [service.completion(self.project.id, code) for code in PHASE_ARTIFACTS[self.phase]]
        completion = round(sum(values) / len(values)) if values else 100
        self.completion.setValue(completion)
        self.completion.setFormat(f"Complétude de phase : {completion} %")
        problems = ValidationService(self.session).validate_project(self.project.id)
        errors = sum(item.severity == "ERROR" for item in problems)
        warnings = sum(item.severity == "WARNING" for item in problems)
        self.validation_summary.setText(
            f"Validation courante : {errors} erreur(s), {warnings} avertissement(s). "
            "Les contrôles détaillés restent accessibles dans la page Validation."
        )
        self.overview.reload()
        for editor in self.editors:
            editor.reload()
        if self.gate:
            self.gate.reload()
        if self.acceptance:
            self.acceptance.reload()
        if self.closing:
            self.closing.reload()
