from pathlib import Path

from sqlalchemy import inspect, text

from pm2.application.context import ApplicationContext
from pm2.infrastructure.database import Database

EXPECTED_TABLES = {
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


def test_alembic_initial_migration(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config

    destination = tmp_path / "migrated.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{destination}")
    command.upgrade(config, "head")
    from sqlalchemy import create_engine

    migrated_tables = set(inspect(create_engine(f"sqlite:///{destination}")).get_table_names())
    assert migrated_tables == EXPECTED_TABLES | {"alembic_version"}


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
