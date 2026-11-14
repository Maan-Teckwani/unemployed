"""Interview preparation and user-supplied company intelligence.

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.types

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_prep",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("talking_points", sa.JSON(), nullable=False),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["resume_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_table(
        "company_intel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_intel_company", "company_intel", ["company_name"])


def downgrade() -> None:
    op.drop_index("ix_company_intel_company", table_name="company_intel")
    op.drop_table("company_intel")
    op.drop_table("interview_prep")
