from __future__ import annotations

import builtins
import getpass
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    AuditEventModel,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _object_label(entity_type: str, entity_id: str, old: Any, new: Any) -> str:
    values = {**_mapping(old), **_mapping(new)}
    identity = next(
        (
            str(values[key])
            for key in ("reference", "code", "gate_code", "filename", "name", "title")
            if values.get(key)
        ),
        entity_id[:8],
    )
    labels = {
        "change": "ChangeRequest",
        "risk": "Risk",
        "issue": "Issue",
        "decision": "Decision",
        "requirement": "Requirement",
        "deliverable": "Deliverable",
        "document": "Document",
        "project": "Project",
        "baseline": "Baseline",
        "gate": "Gate",
    }
    return f"{labels.get(entity_type, entity_type.replace('_', ' ').title())} {identity}"


@dataclass(frozen=True, slots=True)
class AuditFieldChange:
    field: str
    before: Any
    after: Any


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        project_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        old: Any = None,
        new: Any = None,
        actor: str = "local",
        origin: str = "application",
        reason: str = "",
        object_label: str | None = None,
    ) -> AuditEventModel:
        actor = actor.strip()
        if not actor or actor == "local":
            actor = getpass.getuser() or "local"
        inferred_reason = _mapping(new).get("reason") or _mapping(new).get("comments") or ""
        event = AuditEventModel(
            project_id=project_id,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            object_label=object_label or _object_label(entity_type, entity_id, old, new),
            action=action,
            origin=origin.strip() or "application",
            reason=reason.strip() or str(inferred_reason),
            old_value_json=_json(old) if old is not None else None,
            new_value_json=_json(new) if new is not None else None,
        )
        self.session.add(event)
        self.session.flush()
        return event


class AuditTrailService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        project_id: str,
        *,
        entity_type: str | None = None,
        actor: str | None = None,
        search: str = "",
        limit: int = 2_000,
    ) -> builtins.list[AuditEventModel]:
        statement = select(AuditEventModel).where(AuditEventModel.project_id == project_id)
        if entity_type:
            statement = statement.where(AuditEventModel.entity_type == entity_type)
        if actor:
            statement = statement.where(AuditEventModel.actor == actor)
        if search.strip():
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    AuditEventModel.object_label.ilike(pattern),
                    AuditEventModel.action.ilike(pattern),
                    AuditEventModel.reason.ilike(pattern),
                )
            )
        return builtins.list(
            self.session.scalars(
                statement.order_by(AuditEventModel.timestamp.desc()).limit(limit)
            ).all()
        )

    def actors(self, project_id: str) -> builtins.list[str]:
        return builtins.list(
            self.session.scalars(
                select(AuditEventModel.actor)
                .where(AuditEventModel.project_id == project_id)
                .distinct()
                .order_by(AuditEventModel.actor)
            ).all()
        )

    def entity_types(self, project_id: str) -> builtins.list[str]:
        return builtins.list(
            self.session.scalars(
                select(AuditEventModel.entity_type)
                .where(AuditEventModel.project_id == project_id)
                .distinct()
                .order_by(AuditEventModel.entity_type)
            ).all()
        )

    @staticmethod
    def values(event: AuditEventModel) -> tuple[Any, Any]:
        def load(raw: str | None) -> Any:
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

        return load(event.old_value_json), load(event.new_value_json)

    @classmethod
    def changes(cls, event: AuditEventModel) -> tuple[AuditFieldChange, ...]:
        before, after = cls.values(event)
        if isinstance(before, dict) or isinstance(after, dict):
            old_values = _mapping(before)
            new_values = _mapping(after)
            return tuple(
                AuditFieldChange(field, old_values.get(field), new_values.get(field))
                for field in sorted(old_values.keys() | new_values.keys())
                if old_values.get(field) != new_values.get(field)
            )
        if before != after:
            return (AuditFieldChange("value", before, after),)
        return ()

    def export_json(self, project_id: str, destination: Path) -> Path:
        events = self.list(project_id)
        payload = [
            {
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "user": event.actor,
                "origin": event.origin,
                "object": event.object_label,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "action": event.action,
                "reason": event.reason,
                "before": self.values(event)[0],
                "after": self.values(event)[1],
            }
            for event in events
        ]
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(destination)
        return destination
