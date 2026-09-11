from __future__ import annotations

import json
from contextlib import suppress
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Column

from pm2.application.crud import EntityCrudService
from pm2.application.validation import ValidationService
from pm2.domain.workflows import DEFAULT_WORKFLOW_ENGINE
from pm2.infrastructure.orm import ALL_MODELS_BY_TABLE, Base, TraceLinkModel

FRIENDLY_NAMES = {
    "projects": "Projets",
    "phases": "Phases",
    "persons": "Personnes",
    "roles": "Rôles",
    "project_role_assignments": "Affectations de rôles",
    "stakeholders": "Parties prenantes",
    "responsibility_assignments": "Responsabilités RCmSCI",
    "wbs_nodes": "Nœuds WBS",
    "tasks": "Tâches",
    "task_dependencies": "Dépendances de tâches",
    "deliverables": "Livrables",
    "requirements": "Exigences",
    "requirement_tasks": "Liens exigence-tâche",
    "requirement_deliverables": "Liens exigence-livrable",
    "risks": "Risques",
    "risk_actions": "Actions de risque",
    "issues": "Problèmes",
    "issue_actions": "Actions de problème",
    "decisions": "Décisions",
    "changes": "Modifications",
    "change_impacts": "Impacts de modification",
    "change_approvals": "Approbations de modification",
    "quality_controls": "Contrôles qualité",
    "quality_findings": "Constats qualité",
    "quality_actions": "Actions qualité",
    "acceptance_plans": "Plans d’acceptation",
    "acceptance_criteria": "Critères d’acceptation",
    "acceptance_tests": "Tests d’acceptation",
    "acceptances": "Acceptations",
    "transition_activities": "Activités de transition",
    "implementation_activities": "Activités de mise en œuvre",
    "meetings": "Réunions",
    "meeting_participants": "Participants aux réunions",
    "meeting_actions": "Actions de réunion",
    "communications": "Communications",
    "reports": "Rapports",
    "documents": "Documents",
    "document_versions": "Versions documentaires",
    "document_links": "Liens documentaires",
    "gate_reviews": "Revues de gate",
    "gate_checklist_items": "Éléments de checklist",
    "gate_decisions": "Décisions de gate",
    "trace_links": "Liens de traçabilité",
    "lessons_learned": "Leçons apprises",
    "recommendations": "Recommandations",
    "audit_events": "Événements d’audit",
    "settings": "Paramètres",
}

FIELD_LABELS = {
    "code": "Code",
    "name": "Nom",
    "title": "Titre",
    "description": "Description",
    "status": "Statut",
    "owner": "Responsable",
    "priority": "Priorité",
    "probability": "Probabilité",
    "impact": "Impact",
    "score": "Score",
    "cause": "Cause",
    "consequence": "Conséquence",
    "strategy": "Stratégie",
    "requester": "Demandeur",
    "request_date": "Date de demande",
    "decision_owner": "Responsable de décision",
    "decision_date": "Date de décision",
    "project_id": "Projet",
    "person_id": "Personne",
    "role_code": "Rôle",
    "due_date": "Échéance",
    "planned_start": "Début planifié",
    "planned_end": "Fin planifiée",
    "actual_start": "Début réel",
    "actual_end": "Fin réelle",
    "created_at": "Créé le",
    "updated_at": "Modifié le",
    "deleted_at": "Supprimé le",
    "archived": "Archivé",
    "progress_percent": "Avancement (%)",
}

WORKFLOW_KIND_BY_TABLE = {
    "risks": "risk",
    "issues": "issue",
    "decisions": "decision",
    "changes": "change",
    "requirements": "requirement",
    "deliverables": "deliverable",
    "documents": "document",
    "meetings": "meeting",
}


def entity_label(entity: Base) -> str:
    identity = str(getattr(entity, "id", getattr(entity, "code", "")))
    for attribute in ("code", "reference", "name", "title", "subject", "key"):
        value = getattr(entity, attribute, None)
        if value:
            return f"{value} · {identity[:8]}"
    return identity


class EntityEditDialog(QDialog):
    def __init__(
        self,
        session: Session,
        table_name: str,
        entity: Base | None = None,
        *,
        project_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.session, self.table_name, self.entity = session, table_name, entity
        self.project_id = project_id
        self.model = ALL_MODELS_BY_TABLE[table_name]
        self.widgets: dict[str, QWidget] = {}
        self.columns: dict[str, Column[Any]] = {}
        action = "Modifier" if entity else "Créer"
        self.setWindowTitle(f"{action} — {FRIENDLY_NAMES.get(table_name, table_name)}")
        self.resize(620, 680)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Les champs marqués * sont obligatoires. Les transitions de statut restent contrôlées "
            "par les services métier."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        container = QWidget()
        form = QFormLayout(container)
        for column in self.model.__table__.columns:
            if not self._show_column(column):
                continue
            widget = self._widget_for(column)
            self.widgets[column.name] = widget
            self.columns[column.name] = column
            required = not column.nullable and column.default is None and not column.primary_key
            label = FIELD_LABELS.get(column.name, column.name.replace("_", " ").capitalize())
            form.addRow(label + (" *" if required else ""), widget)
        root.addWidget(container)
        root.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _show_column(self, column: Column[Any]) -> bool:
        if column.name in {
            "project_id",
            "created_at",
            "updated_at",
            "deleted_at",
            "status",
            "current_phase",
            "methodology_id",
            "methodology_version",
        }:
            return False
        return not (column.name == "id" and column.default is not None)

    def _widget_for(self, column: Column[Any]) -> QWidget:
        current = getattr(self.entity, column.name, None) if self.entity else None
        if column.foreign_keys:
            target_table = next(iter(column.foreign_keys)).column.table.name
            combo = QComboBox()
            if column.nullable:
                combo.addItem("— Aucun —", None)
            candidates = EntityCrudService(self.session, self.project_id).list(
                target_table, include_archived=False
            )
            for candidate in candidates:
                candidate_id = getattr(candidate, "id", getattr(candidate, "code", None))
                combo.addItem(entity_label(candidate), candidate_id)
            if current is not None:
                index = combo.findData(current)
                if index >= 0:
                    combo.setCurrentIndex(index)
            return combo
        if isinstance(column.type, Boolean):
            checkbox = QCheckBox()
            checkbox.setChecked(bool(current))
            return checkbox
        if column.name == "status":
            combo = QComboBox()
            kind = WORKFLOW_KIND_BY_TABLE.get(self.table_name)
            statuses = list(DEFAULT_WORKFLOW_ENGINE.workflows.get(kind or "", {}))
            statuses.extend(["DRAFT", "OPEN", "PLANNED", "ACTIVE", "PENDING", "NOT_STARTED"])
            for value in dict.fromkeys(statuses):
                combo.addItem(value)
            if current:
                index = combo.findText(str(current))
                if index < 0:
                    combo.addItem(str(current))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        if isinstance(column.type, Text):
            editor = QPlainTextEdit()
            editor.setMaximumHeight(90)
            editor.setPlainText(str(current or ""))
            return editor
        editor = QLineEdit()
        editor.setText(str(current) if current is not None else "")
        if isinstance(column.type, (Date, DateTime)):
            editor.setPlaceholderText(
                "AAAA-MM-JJ" if isinstance(column.type, Date) else "AAAA-MM-JJTHH:MM:SS"
            )
        return editor

    def _validate(self) -> None:
        try:
            self.values()
        except ValueError as exc:
            QMessageBox.warning(self, "Valeur invalide", str(exc))
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, widget in self.widgets.items():
            column = self.columns[name]
            if isinstance(widget, QCheckBox):
                result[name] = widget.isChecked()
                continue
            if isinstance(widget, QComboBox):
                result[name] = widget.currentData() if column.foreign_keys else widget.currentText()
                continue
            raw = (
                widget.toPlainText().strip()
                if isinstance(widget, QPlainTextEdit)
                else widget.text().strip()
            )
            if not raw:
                if column.nullable:
                    result[name] = None
                    continue
                if column.default is not None and self.entity is None:
                    continue
                if not column.primary_key or column.default is None:
                    raise ValueError(f"Le champ {FIELD_LABELS.get(name, name)} est obligatoire.")
            result[name] = self._convert(column, raw)
        return result

    @staticmethod
    def _convert(column: Column[Any], raw: str) -> Any:
        try:
            if isinstance(column.type, Integer):
                return int(raw)
            if isinstance(column.type, Numeric):
                return Decimal(raw)
            if isinstance(column.type, DateTime):
                return datetime.fromisoformat(raw)
            if isinstance(column.type, Date):
                return date.fromisoformat(raw)
            if isinstance(column.type, (String, Text)):
                return raw
            return raw
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"Valeur invalide pour {column.name} : {raw}") from exc


class EntityCatalogPage(QWidget):
    changed = Signal()

    def __init__(self, session: Session, project_id: str) -> None:
        super().__init__()
        self.session, self.project_id = session, project_id
        self.service = EntityCrudService(session, project_id)
        root = QVBoxLayout(self)
        title = QLabel("Catalogue des entités & audit")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        actions = QHBoxLayout()
        self.selector = QComboBox()
        for table_name in sorted(
            ALL_MODELS_BY_TABLE, key=lambda value: FRIENDLY_NAMES.get(value, value)
        ):
            self.selector.addItem(FRIENDLY_NAMES.get(table_name, table_name), table_name)
        self.selector.currentIndexChanged.connect(self.reload)
        self.include_archived = QCheckBox("Inclure les archivés")
        self.include_archived.toggled.connect(self.reload)
        add = QPushButton("Créer")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._create)
        edit = QPushButton("Modifier")
        edit.clicked.connect(self._edit)
        remove = QPushButton("Archiver / supprimer")
        remove.clicked.connect(self._remove)
        restore = QPushButton("Restaurer")
        restore.clicked.connect(self._restore)
        actions.addWidget(self.selector)
        actions.addWidget(self.include_archived)
        actions.addStretch()
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addWidget(remove)
        actions.addWidget(restore)
        root.addLayout(actions)
        splitter = QSplitter()
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._load_detail)
        self.table.doubleClicked.connect(self._edit)
        splitter.addWidget(self.table)
        self.detail_tabs = QTabWidget()
        self.data_view = QTableWidget(0, 2)
        self.data_view.setHorizontalHeaderLabels(["Champ", "Valeur"])
        self.data_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.relations_view = QTableWidget(0, 3)
        self.relations_view.setHorizontalHeaderLabels(["Source", "Relation", "Cible"])
        self.relations_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.validation_view = QTableWidget(0, 3)
        self.validation_view.setHorizontalHeaderLabels(["Sévérité", "Code", "Message"])
        self.validation_view.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.audit_view = QTableWidget(0, 4)
        self.audit_view.setHorizontalHeaderLabels(["Date", "Acteur", "Action", "Modifications"])
        self.audit_view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.detail_tabs.addTab(self.data_view, "Données")
        relations_index = self.detail_tabs.addTab(self.relations_view, "Relations")
        self.detail_tabs.addTab(self.validation_view, "Validation")
        audit_index = self.detail_tabs.addTab(self.audit_view, "Audit")
        self.detail_tabs.setTabToolTip(relations_index, "Relations / Traçabilité")
        self.detail_tabs.setTabToolTip(audit_index, "Historique / Audit")
        splitter.addWidget(self.detail_tabs)
        splitter.setSizes([760, 520])
        root.addWidget(splitter, 1)
        self.reload()

    def table_name(self) -> str:
        return str(self.selector.currentData())

    def _selected_identity(self) -> str | None:
        row = self.table.currentRow()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) if row >= 0 else None

    def _create(self) -> None:
        controlled = {
            "projects",
            "phases",
            "change_approvals",
            "acceptances",
            "gate_reviews",
            "gate_checklist_items",
            "gate_decisions",
            "audit_events",
        }
        if self.table_name() in controlled:
            QMessageBox.information(
                self,
                "Opération contrôlée",
                "Cette entité est créée par son assistant ou son service métier afin de garantir les règles et l’audit.",
            )
            return
        dialog = EntityEditDialog(
            self.session, self.table_name(), project_id=self.project_id, parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.service.create(self.table_name(), dialog.values())
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Création impossible", str(exc))

    def _edit(self, *_args: Any) -> None:
        identity = self._selected_identity()
        if not identity:
            return
        entity = self.service.require(self.table_name(), identity)
        dialog = EntityEditDialog(
            self.session,
            self.table_name(),
            entity,
            project_id=self.project_id,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.service.update(self.table_name(), identity, dialog.values())
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Modification impossible", str(exc))

    def _remove(self) -> None:
        identity = self._selected_identity()
        if not identity:
            return
        answer = QMessageBox.question(
            self,
            "Confirmer",
            "Archiver cet élément, ou le supprimer s'il est strictement dépendant ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.remove(self.table_name(), identity)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Opération impossible", str(exc))

    def _restore(self) -> None:
        identity = self._selected_identity()
        if not identity:
            return
        try:
            self.service.restore(self.table_name(), identity)
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Restauration impossible", str(exc))

    def reload(self) -> None:
        if self.selector.currentIndex() < 0:
            return
        selected_identity = self._selected_identity()
        model = ALL_MODELS_BY_TABLE[self.table_name()]
        preferred = ("code", "reference", "name", "title", "status", "owner")
        all_columns = list(model.__table__.columns)
        columns = [
            *(
                model.__table__.columns[name]
                for name in preferred
                if name in model.__table__.columns
            ),
            *(column for column in all_columns if column.name not in preferred),
        ][:10]
        rows = self.service.list(
            self.table_name(), include_archived=self.include_archived.isChecked()
        )
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(
            [
                FIELD_LABELS.get(column.name, column.name.replace("_", " ").capitalize())
                for column in columns
            ]
        )
        self.table.setRowCount(len(rows))
        for row_index, entity in enumerate(rows):
            identity = self.service.identity(entity)
            for column_index, column in enumerate(columns):
                item = QTableWidgetItem(str(getattr(entity, column.name, "") or ""))
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, identity)
                self.table.setItem(row_index, column_index, item)
            if identity == selected_identity:
                self.table.selectRow(row_index)
        self._clear_detail()
        if self.table.currentRow() >= 0:
            self._load_detail()

    def _clear_detail(self) -> None:
        for view in (self.data_view, self.relations_view, self.validation_view, self.audit_view):
            view.setRowCount(0)

    def _load_detail(self) -> None:
        identity = self._selected_identity()
        if not identity:
            self._clear_detail()
            return
        entity = self.service.require(self.table_name(), identity)
        columns = list(entity.__table__.columns)
        self.data_view.setRowCount(len(columns))
        for row, column in enumerate(columns):
            self.data_view.setItem(
                row, 0, QTableWidgetItem(FIELD_LABELS.get(column.name, column.name))
            )
            self.data_view.setItem(
                row, 1, QTableWidgetItem(str(getattr(entity, column.name) or ""))
            )
        aliases = {
            self.table_name(),
            self.table_name().rstrip("s"),
            entity.__class__.__name__.removesuffix("Model").lower(),
        }
        links = self.session.scalars(
            select(TraceLinkModel).where(
                TraceLinkModel.project_id == self.project_id,
                or_(
                    TraceLinkModel.source_type.in_(aliases)
                    & (TraceLinkModel.source_id == identity),
                    TraceLinkModel.target_type.in_(aliases)
                    & (TraceLinkModel.target_id == identity),
                ),
            )
        ).all()
        self.relations_view.setRowCount(len(links))
        for row, link in enumerate(links):
            for column, value in enumerate(
                (
                    f"{link.source_type} · {link.source_id}",
                    link.relation_type,
                    f"{link.target_type} · {link.target_id}",
                )
            ):
                self.relations_view.setItem(row, column, QTableWidgetItem(value))
        problems = [
            item
            for item in ValidationService(self.session).validate_project(self.project_id)
            if item.entity_id == identity or item.entity in aliases
        ]
        self.validation_view.setRowCount(len(problems))
        for row, problem in enumerate(problems):
            for column, value in enumerate((problem.severity, problem.code, problem.message)):
                self.validation_view.setItem(row, column, QTableWidgetItem(value))
        events = self.service.history(self.table_name(), identity)
        self.audit_view.setRowCount(len(events))
        for row, event in enumerate(events):
            changes = event.new_value_json or event.old_value_json or ""
            with suppress(json.JSONDecodeError, TypeError):
                changes = json.dumps(json.loads(changes), ensure_ascii=False, indent=1)
            for column, value in enumerate((event.timestamp, event.actor, event.action, changes)):
                self.audit_view.setItem(row, column, QTableWidgetItem(str(value)))
