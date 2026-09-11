from __future__ import annotations

from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)


class ProjectDialog(QDialog):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet PM²")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.reference = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(90)
        self.pm = QLineEdit()
        self.po = QLineEdit()
        self.budget = QDoubleSpinBox()
        self.budget.setRange(0, 999_999_999_999.99)
        self.budget.setDecimals(2)
        self.currency = QComboBox()
        self.currency.addItems(["EUR", "CHF", "USD", "GBP"])
        self.start = QDateEdit(QDate.currentDate())
        self.start.setCalendarPopup(True)
        self.end = QDateEdit(QDate.currentDate().addMonths(6))
        self.end.setCalendarPopup(True)
        self.methodology = QLineEdit("PM² v3.1 — français")
        self.methodology.setReadOnly(True)
        for label, widget in (
            ("Nom *", self.name),
            ("Référence *", self.reference),
            ("Description", self.description),
            ("Chef de Projet (PM)", self.pm),
            ("Porteur du Projet (PO)", self.po),
            ("Budget approuvé", self.budget),
            ("Devise", self.currency),
            ("Date de début", self.start),
            ("Date de fin cible", self.end),
            ("Méthodologie", self.methodology),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Créer le projet")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.name.text().strip() or not self.reference.text().strip():
            QMessageBox.warning(
                self, "Données requises", "Le nom et la référence sont obligatoires."
            )
            return
        if self.end.date() < self.start.date():
            QMessageBox.warning(self, "Dates invalides", "La fin cible doit suivre le début.")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name.text().strip(),
            "reference": self.reference.text().strip(),
            "description": self.description.toPlainText().strip(),
            "project_manager": self.pm.text().strip(),
            "project_owner": self.po.text().strip(),
            "approved_budget": Decimal(str(self.budget.value())),
            "currency": self.currency.currentText(),
            "start_date": self.start.date().toPython(),
            "target_end_date": self.end.date().toPython(),
        }


class RegisterItemDialog(QDialog):
    def __init__(self, kind: str, parent: Any = None) -> None:
        super().__init__(parent)
        self.kind = kind
        labels = {
            "risk": "risque",
            "issue": "problème",
            "decision": "décision",
            "change": "modification",
        }
        self.setWindowTitle(f"Nouveau {labels[kind]}")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.code = QLineEdit()
        self.title = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(90)
        form.addRow("Code *", self.code)
        form.addRow("Titre *", self.title)
        form.addRow("Description", self.description)
        self.owner = QLineEdit()
        form.addRow("Responsable", self.owner)
        self.priority = QComboBox()
        self.priority.addItems(["", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
        if kind in {"issue", "change"}:
            form.addRow("Priorité", self.priority)
        self.probability = QSpinBox()
        self.probability.setRange(1, 5)
        self.impact = QSpinBox()
        self.impact.setRange(1, 5)
        self.strategy = QPlainTextEdit()
        self.strategy.setMaximumHeight(70)
        if kind == "risk":
            form.addRow("Probabilité (1–5)", self.probability)
            form.addRow("Impact (1–5)", self.impact)
            form.addRow("Stratégie", self.strategy)
        self.outcome = QPlainTextEdit()
        self.outcome.setMaximumHeight(70)
        if kind == "decision":
            form.addRow("Résultat", self.outcome)
        self.reason = QPlainTextEdit()
        self.reason.setMaximumHeight(70)
        if kind == "change":
            form.addRow("Motif", self.reason)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.code.text().strip() or not self.title.text().strip():
            QMessageBox.warning(self, "Données requises", "Le code et le titre sont obligatoires.")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        common: dict[str, Any] = {
            "code": self.code.text().strip(),
            "title": self.title.text().strip(),
            "description": self.description.toPlainText().strip(),
        }
        if self.kind in {"risk", "issue"}:
            common["owner"] = self.owner.text().strip() or None
        if self.kind == "risk":
            common.update(
                probability=self.probability.value(),
                impact=self.impact.value(),
                strategy=self.strategy.toPlainText().strip(),
            )
        elif self.kind == "issue":
            common.update(priority=self.priority.currentText() or None, impact="")
        elif self.kind == "decision":
            common.update(outcome=self.outcome.toPlainText().strip(), rationale="")
        else:
            common.update(
                priority=self.priority.currentText() or None,
                reason=self.reason.toPlainText().strip(),
            )
        return common


class WbsNodeDialog(QDialog):
    def __init__(self, parent: Any = None, *, node: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouvel élément du plan de travail")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.node_type = QComboBox()
        self.node_type.addItem("Lot de travaux", "work_package")
        self.node_type.addItem("Tâche", "task")
        self.node_type.addItem("Jalon", "milestone")
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(80)
        self.start = QDateEdit(QDate.currentDate())
        self.start.setCalendarPopup(True)
        self.end = QDateEdit(QDate.currentDate().addDays(5))
        self.end.setCalendarPopup(True)
        self.progress = QSpinBox()
        self.progress.setRange(0, 100)
        self.cost = QDoubleSpinBox()
        self.cost.setRange(0, 999_999_999)
        if node is not None:
            self.setWindowTitle("Modifier l’élément du plan de travail")
            self.code.setText(node.code)
            self.name.setText(node.name)
            self.description.setPlainText(node.description or "")
            type_index = self.node_type.findData(node.node_type)
            if type_index >= 0:
                self.node_type.setCurrentIndex(type_index)
            self.node_type.setEnabled(False)
            if node.task:
                if node.task.planned_start:
                    value = node.task.planned_start
                    self.start.setDate(QDate(value.year, value.month, value.day))
                if node.task.planned_end:
                    value = node.task.planned_end
                    self.end.setDate(QDate(value.year, value.month, value.day))
                self.progress.setValue(node.task.progress_percent)
                self.cost.setValue(float(node.task.planned_cost))
        for label, widget in (
            ("Code *", self.code),
            ("Nom *", self.name),
            ("Type", self.node_type),
            ("Description", self.description),
            ("Début planifié", self.start),
            ("Fin planifiée", self.end),
            ("Avancement (%)", self.progress),
            ("Coût planifié", self.cost),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.code.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "Données requises", "Le code et le nom sont obligatoires.")
            return
        if self.end.date() < self.start.date():
            QMessageBox.warning(self, "Dates invalides", "La fin doit suivre le début.")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        node_type = str(self.node_type.currentData())
        return {
            "code": self.code.text().strip(),
            "name": self.name.text().strip(),
            "node_type": node_type,
            "description": self.description.toPlainText().strip(),
            "planned_start": self.start.date().toPython(),
            "planned_end": self.start.date().toPython()
            if node_type == "milestone"
            else self.end.date().toPython(),
            "progress_percent": self.progress.value(),
            "planned_cost": Decimal(str(self.cost.value())),
        }


class TraceLinkDialog(QDialog):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Créer un lien de traçabilité")
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.source_type = QComboBox()
        self.source_type.addItems(
            [
                "requirement",
                "deliverable",
                "task",
                "risk",
                "issue",
                "decision",
                "change",
                "document",
            ]
        )
        self.source_id = QLineEdit()
        self.target_type = QComboBox()
        self.target_type.addItems(
            [
                "task",
                "deliverable",
                "acceptance_test",
                "decision",
                "change",
                "document",
                "transition_activity",
            ]
        )
        self.target_id = QLineEdit()
        self.relation = QComboBox()
        self.relation.addItems(
            [
                "supports",
                "derives_from",
                "impacts",
                "mitigates",
                "resolves",
                "decides",
                "implements",
                "verifies",
                "accepted_by",
                "produces",
                "depends_on",
                "assigned_to",
                "discussed_in",
                "referenced_by",
            ]
        )
        for label, widget in (
            ("Type source", self.source_type),
            ("Identifiant source *", self.source_id),
            ("Relation", self.relation),
            ("Type cible", self.target_type),
            ("Identifiant cible *", self.target_id),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.source_id.text().strip() or not self.target_id.text().strip():
            QMessageBox.warning(
                self, "Données requises", "Les deux identifiants sont obligatoires."
            )
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {
            "source_type": self.source_type.currentText(),
            "source_id": self.source_id.text().strip(),
            "target_type": self.target_type.currentText(),
            "target_id": self.target_id.text().strip(),
            "relation_type": self.relation.currentText(),
        }
