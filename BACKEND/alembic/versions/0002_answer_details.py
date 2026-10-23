"""answers: as_of date and the full record as JSON

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("answers", sa.Column("as_of", sa.Date(), nullable=True))
    op.add_column("answers", sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("answers", "details")
    op.drop_column("answers", "as_of")
