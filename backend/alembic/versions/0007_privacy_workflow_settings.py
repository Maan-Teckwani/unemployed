"""privacy controls and personal workflow settings

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_application_goal", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("follow_up_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("week_starts_monday", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_table("workflow_settings")
