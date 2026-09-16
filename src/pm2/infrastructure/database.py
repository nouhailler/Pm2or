from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
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
        self.upgrade_schema()

    @staticmethod
    def _migration_directory() -> Path:
        candidates = (
            Path(__file__).resolve().parents[3] / "migrations",
            Path(__file__).resolve().parents[1] / "migrations",
        )
        for candidate in candidates:
            if (candidate / "env.py").is_file():
                return candidate
        raise RuntimeError("Les migrations Alembic de PM² Desktop sont introuvables.")

    def upgrade_schema(self) -> None:
        """Bring the database to the current schema revision."""
        if self.path is None:
            # Alembic would open another connection and therefore another in-memory database.
            Base.metadata.create_all(self.engine)
            return
        configuration = Config()
        configuration.set_main_option("script_location", str(self._migration_directory()))
        configuration.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{self.path}")
        command.upgrade(configuration, "head")

    def ensure_schema_compatibility(self) -> None:
        """Compatibility shim for callers predating automatic Alembic migrations."""
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
