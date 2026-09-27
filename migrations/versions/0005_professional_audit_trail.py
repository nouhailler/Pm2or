"""Enrichit l'audit avec objet, origine et raison.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("audit_events")}
    if "object_label" not in columns:
        op.add_column(
            "audit_events",
            sa.Column("object_label", sa.String(length=255), nullable=False, server_default=""),
        )
    if "origin" not in columns:
        op.add_column(
            "audit_events",
            sa.Column(
                "origin",
                sa.String(length=80),
                nullable=False,
                server_default="application",
            ),
        )
        op.create_index("ix_audit_events_origin", "audit_events", ["origin"])
    if "reason" not in columns:
        op.add_column(
            "audit_events",
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        )
    op.execute(
        """
        UPDATE audit_events
        SET object_label = entity_type || ' ' || substr(entity_id, 1, 8)
        WHERE object_label = ''
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_immutable_update
        BEFORE UPDATE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit event immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_immutable_delete
        BEFORE DELETE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit event immutable');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable_update")
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("audit_events")
    }
    if "reason" in columns:
        op.drop_column("audit_events", "reason")
    if "origin" in columns:
        op.drop_index("ix_audit_events_origin", table_name="audit_events")
        op.drop_column("audit_events", "origin")
    if "object_label" in columns:
        op.drop_column("audit_events", "object_label")
