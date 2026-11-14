"""application answer library and analytics history

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="general"),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("explicit_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "application_answer_uses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("application_answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_application_answer_uses_answer_id", "application_answer_uses", ["answer_id"])
    op.create_index("ix_application_answer_uses_job_id", "application_answer_uses", ["job_id"])
    op.create_table(
        "application_status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_application_status_events_job_id", "application_status_events", ["job_id"])
    op.create_index("ix_application_status_events_occurred_at", "application_status_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_application_status_events_occurred_at", table_name="application_status_events")
    op.drop_index("ix_application_status_events_job_id", table_name="application_status_events")
    op.drop_table("application_status_events")
    op.drop_index("ix_application_answer_uses_job_id", table_name="application_answer_uses")
    op.drop_index("ix_application_answer_uses_answer_id", table_name="application_answer_uses")
    op.drop_table("application_answer_uses")
    op.drop_table("application_answers")
