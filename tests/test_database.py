from pathlib import Path

from sqlalchemy import inspect, text

from pm2.application.context import ApplicationContext

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
