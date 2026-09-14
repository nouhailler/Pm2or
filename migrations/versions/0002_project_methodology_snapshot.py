"""Fige la méthodologie de chaque projet.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("projects")}
    if "methodology_hash" not in columns:
        op.add_column(
            "projects",
            sa.Column("methodology_hash", sa.String(length=64), nullable=False, server_default=""),
        )
    if "methodology_snapshot" not in columns:
        op.add_column(
            "projects",
            sa.Column("methodology_snapshot", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}
    if "methodology_snapshot" in columns:
        op.drop_column("projects", "methodology_snapshot")
    if "methodology_hash" in columns:
        op.drop_column("projects", "methodology_hash")
