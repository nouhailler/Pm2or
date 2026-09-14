from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from pm2.infrastructure.orm import Base


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if str(path) != ":memory:" else None
        url = (
            "sqlite+pysqlite:///:memory:"
            if self.path is None
            else f"sqlite+pysqlite:///{self.path}"
        )
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, future=True)
        event.listen(self.engine, "connect", self._enable_foreign_keys)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self.ensure_schema_compatibility()

    def ensure_schema_compatibility(self) -> None:
        """Apply additive compatibility fixes needed before Alembic can be run explicitly."""
        inspector = inspect(self.engine)
        if "projects" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("projects")}
        additions = {
            "methodology_hash": (
                "ALTER TABLE projects ADD COLUMN methodology_hash VARCHAR(64) NOT NULL DEFAULT ''"
            ),
            "methodology_snapshot": (
                "ALTER TABLE projects ADD COLUMN methodology_snapshot TEXT NOT NULL DEFAULT ''"
            ),
        }
        with self.engine.begin() as connection:
            for name, statement in additions.items():
                if name not in columns:
                    connection.execute(text(statement))

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
