import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DatabaseError

from pm2.application.context import ApplicationContext
from pm2.infrastructure.database import Database

EXPECTED_TABLES = {
    "alembic_version",
    "attachments",
    "baselines",
    "projects",
    "phases",
    "persons",
    "roles",
    "project_role_assignments",
    "stakeholders",
    "responsibility_assignments",
    "wbs_nodes",
    "tasks",
    "task_dependencies",
    "deliverables",
    "requirements",
    "requirement_tasks",
    "requirement_deliverables",
    "risks",
    "risk_actions",
    "issues",
    "issue_actions",
    "decisions",
    "changes",
    "change_impacts",
    "change_approvals",
    "quality_controls",
    "quality_findings",
    "quality_actions",
    "acceptance_plans",
    "acceptance_criteria",
    "acceptance_tests",
    "acceptances",
    "transition_activities",
    "implementation_activities",
    "meetings",
    "meeting_participants",
    "meeting_actions",
    "communications",
    "reports",
    "documents",
    "document_versions",
    "document_links",
    "gate_reviews",
    "gate_checklist_items",
    "gate_decisions",
    "trace_links",
    "lessons_learned",
    "recommendations",
    "audit_events",
    "settings",
}


def test_complete_schema_and_foreign_keys(context: ApplicationContext) -> None:
    assert set(inspect(context.database.engine).get_table_names()) == EXPECTED_TABLES
    with context.database.engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"


def test_alembic_initial_migration(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config

    destination = tmp_path / "migrated.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{destination}")
    command.upgrade(config, "head")
    from sqlalchemy import create_engine

    migrated_tables = set(inspect(create_engine(f"sqlite:///{destination}")).get_table_names())
    assert migrated_tables == EXPECTED_TABLES


def test_runtime_adds_methodology_snapshot_columns_to_legacy_database(tmp_path: Path) -> None:
    database = Database(tmp_path / "legacy.db")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id VARCHAR(36) PRIMARY KEY, "
                "methodology_id VARCHAR(40) NOT NULL, "
                "methodology_version VARCHAR(20) NOT NULL"
                ")"
            )
        )

    database.ensure_schema_compatibility()

    columns = {column["name"] for column in inspect(database.engine).get_columns("projects")}
    assert {"methodology_hash", "methodology_snapshot"} <= columns
    database.dispose()


def test_open_rejects_foreign_database_without_modifying_its_schema(tmp_path: Path) -> None:
    destination = tmp_path / "foreign.db"
    database = Database(destination)
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE notes (id INTEGER PRIMARY KEY, value TEXT)"))
    database.dispose()

    with pytest.raises(ValueError, match="n'est pas une base PM²"):
        ApplicationContext.open(destination, create=False)

    probe = Database(destination)
    assert inspect(probe.engine).get_table_names() == ["notes"]
    probe.dispose()


def test_failed_migration_restores_database_and_keeps_backup(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "legacy.db"
    with sqlite3.connect(destination) as connection:
        connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO projects VALUES ('p1', 'Avant migration')")
    original = destination.read_bytes()

    def fail_upgrade(*_args, **_kwargs) -> None:
        destination.write_bytes(b"migration partielle")
        raise RuntimeError("migration simulée")

    monkeypatch.setattr("pm2.infrastructure.database.command.upgrade", fail_upgrade)
    database = Database(destination)
    with pytest.raises(RuntimeError, match="simulée"):
        database.upgrade_schema()

    assert destination.read_bytes() == original
    backups = list(tmp_path.glob("legacy.db.pre-migration-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


@pytest.mark.parametrize("revision", ["0001", "0002", "0003", "0004"])
def test_upgrade_from_every_published_schema_revision(tmp_path: Path, revision: str) -> None:
    destination = tmp_path / f"release-{revision}.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{destination}")
    command.upgrade(config, revision)

    database = Database(destination)
    database.upgrade_schema()
    with database.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
    database.dispose()
    assert len(list(tmp_path.glob(f"release-{revision}.db.pre-migration-*.bak"))) == 1


def test_corrupt_sqlite_is_rejected_without_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "corrupt.db"
    original = b"not a sqlite database"
    destination.write_bytes(original)
    with pytest.raises(DatabaseError):
        ApplicationContext.open(destination, create=False)
    assert destination.read_bytes() == original
