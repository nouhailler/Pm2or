"""Schéma initial complet PM² Desktop V0.1.

Revision ID: 0001
Revises: None
"""

from alembic import op

from pm2.infrastructure.orm import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Base.metadata is the single persistence contract used by runtime and migration.
    # It contains all 47 tables enumerated in 03_DATABASE_SCHEMA.md.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
