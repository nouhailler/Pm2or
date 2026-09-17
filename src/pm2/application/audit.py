from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from pm2.application.traceability import TraceabilityService as TraceabilityService
from pm2.infrastructure.orm import (
    AuditEventModel,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


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
    ) -> AuditEventModel:
        event = AuditEventModel(
            project_id=project_id,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value_json=_json(old) if old is not None else None,
            new_value_json=_json(new) if new is not None else None,
        )
        self.session.add(event)
        self.session.flush()
        return event


