from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pm2.application.services import AuditService
from pm2.infrastructure.orm import ALL_MODELS_BY_TABLE, AuditEventModel, Base, row_to_dict
from pm2.infrastructure.repositories import Repository


class EntityCrudService:
    """CRUD audité commun; les transitions restent réservées aux services métier."""

    PROTECTED_FIELDS = {
        "created_at",
        "updated_at",
        "deleted_at",
        "status",
        "current_phase",
        "methodology_id",
        "methodology_version",
        "methodology_hash",
        "methodology_snapshot",
    }

    def __init__(self, session: Session, project_id: str) -> None:
        self.session = session
        self.project_id = project_id

    def model(self, table_name: str) -> type[Base]:
        try:
            return ALL_MODELS_BY_TABLE[table_name]
        except KeyError as exc:
            raise ValueError(f"Type d'entité inconnu : {table_name}") from exc

    def list(self, table_name: str, *, include_archived: bool = False) -> Sequence[Base]:
        model = self.model(table_name)
        statement = self._project_scope(table_name, select(model))
        if not include_archived and "archived" in model.__table__.columns:
            statement = statement.where(model.__table__.c.archived.is_(False))
        if not include_archived and "deleted_at" in model.__table__.columns:
            statement = statement.where(model.__table__.c.deleted_at.is_(None))
        return self.session.scalars(statement).all()

    def create(self, table_name: str, values: dict[str, Any], *, actor: str = "local") -> Base:
        if table_name == "projects":
            raise ValueError(
                "La création d’un projet doit passer par ProjectService pour figer sa méthodologie."
            )
        model = self.model(table_name)
        allowed = {column.name for column in model.__table__.columns}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Champs inconnus : {', '.join(sorted(unknown))}")
        payload = dict(values)
        if "project_id" in allowed:
            payload["project_id"] = self.project_id
        entity = model(**payload)
        try:
            Repository(self.session, model).add(entity)
        except IntegrityError as exc:
            raise ValueError(self._integrity_message(table_name, exc)) from exc
        AuditService(self.session).record(
            self.project_id,
            table_name,
            self.identity(entity),
            "CREATE",
            new=row_to_dict(entity),
            actor=actor,
        )
        return entity

    def update(
        self, table_name: str, entity_id: str, values: dict[str, Any], *, actor: str = "local"
    ) -> Base:
        model = self.model(table_name)
        entity = self.require(table_name, entity_id)
        old = row_to_dict(entity)
        allowed = {column.name for column in model.__table__.columns} - self.PROTECTED_FIELDS
        for key, value in values.items():
            if key not in allowed or key in {"id", "project_id"}:
                continue
            setattr(entity, key, value)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise ValueError(self._integrity_message(table_name, exc)) from exc
        AuditService(self.session).record(
            self.project_id,
            table_name,
            self.identity(entity),
            "UPDATE",
            old=old,
            new=row_to_dict(entity),
            actor=actor,
        )
        return entity

    def remove(self, table_name: str, entity_id: str, *, actor: str = "local") -> None:
        entity = self.require(table_name, entity_id)
        old = row_to_dict(entity)
        if hasattr(entity, "archived"):
            entity.archived = True
            action = "ARCHIVE"
        else:
            self.session.delete(entity)
            action = "DELETE"
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise ValueError(
                "Suppression impossible : cette entité est encore référencée. "
                "Archivez ou détachez d'abord ses relations."
            ) from exc
        AuditService(self.session).record(
            self.project_id, table_name, entity_id, action, old=old, actor=actor
        )

    def restore(self, table_name: str, entity_id: str, *, actor: str = "local") -> Base:
        entity = self.require(table_name, entity_id)
        if not hasattr(entity, "archived"):
            raise ValueError("Cette entité ne prend pas en charge l'archivage.")
        entity.archived = False
        if hasattr(entity, "deleted_at"):
            entity.deleted_at = None
        AuditService(self.session).record(
            self.project_id, table_name, entity_id, "RESTORE", actor=actor
        )
        self.session.flush()
        return entity

    def require(self, table_name: str, entity_id: str) -> Base:
        model = self.model(table_name)
        primary_key = model.__mapper__.primary_key[0]
        entity = self.session.scalar(
            self._project_scope(table_name, select(model)).where(primary_key == entity_id)
        )
        if entity is None and "code" in model.__table__.columns:
            entity = self.session.scalar(
                self._project_scope(table_name, select(model)).where(
                    model.__table__.c.code == entity_id
                )
            )
        if entity is None:
            raise LookupError(f"{table_name} introuvable : {entity_id}")
        return cast(Base, entity)

    def _project_scope(self, table_name: str, statement: Any) -> Any:
        """Applique le périmètre projet, y compris aux tables enfant sans project_id."""
        model: Any = self.model(table_name)
        tables: dict[str, Any] = ALL_MODELS_BY_TABLE
        if table_name == "projects":
            return statement.where(model.id == self.project_id)
        if "project_id" in model.__table__.columns:
            return statement.where(model.project_id == self.project_id)
        if table_name == "persons":
            assignment = tables["project_role_assignments"]
            return (
                statement.join(assignment, assignment.person_id == model.id)
                .where(assignment.project_id == self.project_id)
                .distinct()
            )
        if table_name == "tasks":
            wbs = tables["wbs_nodes"]
            return statement.join(wbs, model.wbs_node_id == wbs.id).where(
                wbs.project_id == self.project_id
            )
        if table_name == "task_dependencies":
            task = tables["tasks"]
            wbs = tables["wbs_nodes"]
            return (
                statement.join(task, model.predecessor_task_id == task.id)
                .join(wbs, task.wbs_node_id == wbs.id)
                .where(wbs.project_id == self.project_id)
            )
        parent_scopes = {
            "requirement_tasks": ("requirements", "requirement_id"),
            "requirement_deliverables": ("requirements", "requirement_id"),
            "risk_actions": ("risks", "risk_id"),
            "issue_actions": ("issues", "issue_id"),
            "change_impacts": ("changes", "change_id"),
            "change_approvals": ("changes", "change_id"),
            "quality_findings": ("quality_controls", "quality_control_id"),
            "acceptance_criteria": ("deliverables", "deliverable_id"),
            "acceptances": ("deliverables", "deliverable_id"),
            "meeting_participants": ("meetings", "meeting_id"),
            "meeting_actions": ("meetings", "meeting_id"),
            "document_versions": ("documents", "document_id"),
            "document_links": ("documents", "document_id"),
            "gate_checklist_items": ("gate_reviews", "gate_review_id"),
            "gate_decisions": ("gate_reviews", "gate_review_id"),
            "recommendations": ("lessons_learned", "lesson_learned_id"),
        }
        if table_name in parent_scopes:
            parent_name, foreign_key = parent_scopes[table_name]
            parent = tables[parent_name]
            return statement.join(parent, getattr(model, foreign_key) == parent.id).where(
                parent.project_id == self.project_id
            )
        if table_name == "quality_actions":
            finding = tables["quality_findings"]
            control = tables["quality_controls"]
            return (
                statement.join(finding, model.finding_id == finding.id)
                .join(control, finding.quality_control_id == control.id)
                .where(control.project_id == self.project_id)
            )
        if table_name == "acceptance_tests":
            criterion = tables["acceptance_criteria"]
            deliverable = tables["deliverables"]
            return (
                statement.join(criterion, model.criterion_id == criterion.id)
                .join(deliverable, criterion.deliverable_id == deliverable.id)
                .where(deliverable.project_id == self.project_id)
            )
        return statement

    def history(self, table_name: str, entity_id: str) -> Sequence[AuditEventModel]:
        return self.session.scalars(
            select(AuditEventModel)
            .where(
                AuditEventModel.project_id == self.project_id,
                AuditEventModel.entity_id == entity_id,
            )
            .order_by(AuditEventModel.timestamp.desc())
        ).all()

    @staticmethod
    def identity(entity: Base) -> str:
        return str(getattr(entity, "id", getattr(entity, "code", "")))

    @staticmethod
    def _integrity_message(table_name: str, error: IntegrityError) -> str:
        detail = str(error.orig)
        if "UNIQUE" in detail.upper():
            return f"Création impossible dans {table_name} : valeur déjà utilisée."
        if "FOREIGN KEY" in detail.upper():
            return f"Création impossible dans {table_name} : relation inexistante."
        if "NOT NULL" in detail.upper():
            return f"Création impossible dans {table_name} : champ obligatoire absent."
        if "CHECK" in detail.upper():
            return f"Création impossible dans {table_name} : règle de cohérence non satisfaite."
        return f"Création impossible dans {table_name} : {detail}"
