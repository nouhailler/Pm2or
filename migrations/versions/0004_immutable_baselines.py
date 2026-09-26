"""Ajoute des baselines projet réellement immuables.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "baselines" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "baselines",
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("type", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=False),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by", sa.String(length=255), nullable=True),
            sa.Column("hash", sa.String(length=64), nullable=False),
            sa.Column("snapshot", sa.Text(), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.CheckConstraint("length(hash) = 64", name="ck_baseline_hash_length"),
            sa.CheckConstraint("length(trim(created_by)) > 0", name="ck_baseline_created_by"),
            sa.CheckConstraint(
                "(approved_at IS NULL AND approved_by IS NULL) OR "
                "(approved_at IS NOT NULL AND length(trim(approved_by)) > 0)",
                name="ck_baseline_approval_complete",
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "code"),
        )
        op.create_index("ix_baselines_project_id", "baselines", ["project_id"])
        op.create_index("ix_baselines_code", "baselines", ["code"])
    op.execute(
        """
        CREATE TRIGGER baselines_immutable_update
        BEFORE UPDATE ON baselines
        WHEN NOT (
            OLD.approved_at IS NULL
            AND OLD.approved_by IS NULL
            AND NEW.approved_at IS NOT NULL
            AND NEW.approved_by IS NOT NULL
            AND length(trim(NEW.approved_by)) > 0
            AND NEW.id IS OLD.id
            AND NEW.project_id IS OLD.project_id
            AND NEW.code IS OLD.code
            AND NEW.name IS OLD.name
            AND NEW.type IS OLD.type
            AND NEW.created_at IS OLD.created_at
            AND NEW.created_by IS OLD.created_by
            AND NEW.hash IS OLD.hash
            AND NEW.snapshot IS OLD.snapshot
        )
        BEGIN
            SELECT RAISE(ABORT, 'baseline immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER baselines_immutable_delete
        BEFORE DELETE ON baselines
        BEGIN
            SELECT RAISE(ABORT, 'baseline immutable');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS baselines_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS baselines_immutable_update")
    op.drop_index("ix_baselines_code", table_name="baselines")
    op.drop_index("ix_baselines_project_id", table_name="baselines")
    op.drop_table("baselines")
