from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.infrastructure.orm import Base


class Repository[ModelT: Base]:
    """Repository générique utilisé par les services, jamais directement par l'UI."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, entity_id: str) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def require(self, entity_id: str) -> ModelT:
        entity = self.get(entity_id)
        if entity is None:
            raise LookupError(f"{self.model.__name__} introuvable : {entity_id}")
        return entity

    def list(self, *criteria: Any) -> Sequence[ModelT]:
        statement = select(self.model)
        if criteria:
            statement = statement.where(*criteria)
        if hasattr(self.model, "deleted_at"):
            statement = statement.where(self.model.deleted_at.is_(None))
        return self.session.scalars(statement).all()

    def archive(self, entity_id: str) -> ModelT:
        entity = self.require(entity_id)
        if not hasattr(entity, "archived"):
            raise TypeError(f"{self.model.__name__} ne peut pas être archivé.")
        entity.archived = True
        self.session.flush()
        return entity

    def update(self, entity_id: str, **values: Any) -> ModelT:
        entity = self.require(entity_id)
        allowed = {column.name for column in self.model.__table__.columns}
        for name, value in values.items():
            if name not in allowed or name == "id":
                raise ValueError(f"Champ non modifiable : {name}")
            setattr(entity, name, value)
        self.session.flush()
        return entity
