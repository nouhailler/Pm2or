"""Ajoute les ressources, disponibilités et allocations aux tâches.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _create_effort_triggers() -> None:
    op.execute(
        """
        CREATE TRIGGER task_resource_effort_limit_insert
        BEFORE INSERT ON task_resource_allocations
        WHEN (
            (SELECT planned_effort FROM tasks WHERE id = NEW.task_id) <= 0
            OR COALESCE(
                (SELECT SUM(effort_days) FROM task_resource_allocations
                 WHERE task_id = NEW.task_id), 0
            ) + NEW.effort_days >
                (SELECT planned_effort FROM tasks WHERE id = NEW.task_id)
        )
        BEGIN
            SELECT RAISE(ABORT, 'resource allocations exceed planned effort');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER task_resource_effort_limit_update
        BEFORE UPDATE OF task_id, effort_days ON task_resource_allocations
        WHEN (
            (SELECT planned_effort FROM tasks WHERE id = NEW.task_id) <= 0
            OR COALESCE(
                (SELECT SUM(effort_days) FROM task_resource_allocations
                 WHERE task_id = NEW.task_id AND id != OLD.id), 0
            ) + NEW.effort_days >
                (SELECT planned_effort FROM tasks WHERE id = NEW.task_id)
        )
        BEGIN
            SELECT RAISE(ABORT, 'resource allocations exceed planned effort');
        END
        """
    )


def upgrade() -> None:
    # The historical 0001 migration builds the current metadata for a brand-new
    # database. Later migrations therefore remain idempotent for that path.
    if "resources" in sa.inspect(op.get_bind()).get_table_names():
        _create_effort_triggers()
        return
    op.create_table(
        "resources",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "default_availability_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="100",
        ),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "resource_type IN ('PERSON','TEAM','SUPPLIER','EQUIPMENT','BUDGET')",
            name="ck_resource_type",
        ),
        sa.CheckConstraint(
            "default_availability_percent BETWEEN 0 AND 100",
            name="ck_resource_default_availability",
        ),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", "resource_type"),
    )
    op.create_index("ix_resources_archived", "resources", ["archived"])
    op.create_index("ix_resources_person_id", "resources", ["person_id"])
    op.create_index("ix_resources_project_id", "resources", ["project_id"])
    op.create_index("ix_resources_resource_type", "resources", ["resource_type"])

    op.create_table(
        "resource_availabilities",
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("availability_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "availability_percent BETWEEN 0 AND 100",
            name="ck_resource_week_availability",
        ),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id", "week_start"),
    )
    op.create_index(
        "ix_resource_availabilities_resource_id",
        "resource_availabilities",
        ["resource_id"],
    )
    op.create_index(
        "ix_resource_availabilities_week_start",
        "resource_availabilities",
        ["week_start"],
    )

    op.create_table(
        "task_resource_allocations",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("effort_days", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("effort_days > 0", name="ck_task_resource_effort_positive"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "resource_id"),
    )
    op.create_index(
        "ix_task_resource_allocations_resource_id",
        "task_resource_allocations",
        ["resource_id"],
    )
    op.create_index(
        "ix_task_resource_allocations_task_id",
        "task_resource_allocations",
        ["task_id"],
    )
    _create_effort_triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS task_resource_effort_limit_update")
    op.execute("DROP TRIGGER IF EXISTS task_resource_effort_limit_insert")
    op.drop_index(
        "ix_task_resource_allocations_task_id", table_name="task_resource_allocations"
    )
    op.drop_index(
        "ix_task_resource_allocations_resource_id", table_name="task_resource_allocations"
    )
    op.drop_table("task_resource_allocations")
    op.drop_index(
        "ix_resource_availabilities_week_start", table_name="resource_availabilities"
    )
    op.drop_index(
        "ix_resource_availabilities_resource_id", table_name="resource_availabilities"
    )
    op.drop_table("resource_availabilities")
    op.drop_index("ix_resources_resource_type", table_name="resources")
    op.drop_index("ix_resources_project_id", table_name="resources")
    op.drop_index("ix_resources_person_id", table_name="resources")
    op.drop_index("ix_resources_archived", table_name="resources")
    op.drop_table("resources")
