"""skill_roadmaps — multi-skill learning project blueprints

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.db.types import JSONColumn, StringList


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_roadmaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("role_family", sa.String(length=40), nullable=False, server_default="backend"),
        sa.Column("target_skills", StringList, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("estimated_weeks", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("architecture", sa.Text(), nullable=False, server_default=""),
        sa.Column("milestones", JSONColumn, nullable=False),
        sa.Column("engineering_challenges", JSONColumn, nullable=False),
        sa.Column("resume_bullet_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("interview_talking_points", StringList, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_skill_roadmaps_status",
        "skill_roadmaps",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_skill_roadmaps_status", table_name="skill_roadmaps")
    op.drop_table("skill_roadmaps")
