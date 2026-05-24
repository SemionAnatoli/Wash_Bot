"""add claimed_at to notification jobs

Revision ID: 0002_add_claimed_at_to_notification_jobs
Revises: 0001_initial_schema
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_claimed_at_to_notification_jobs"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notification_jobs", sa.Column("claimed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("notification_jobs", "claimed_at")
