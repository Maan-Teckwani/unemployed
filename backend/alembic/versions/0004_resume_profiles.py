"""resume_profiles — role-specific evidence and generated resume variants

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    with op.batch_alter_table("kb_chunks") as batch:
        batch.add_column(sa.Column("profile_id", sa.Integer(), nullable=True))
        batch.create_index("ix_kb_chunks_profile_id", ["profile_id"], unique=False)
        batch.create_foreign_key(
            "fk_kb_chunks_profile_id", "resume_profiles", ["profile_id"], ["id"], ondelete="SET NULL"
        )
    with op.batch_alter_table("resumes") as batch:
        batch.add_column(sa.Column("profile_id", sa.Integer(), nullable=True))
        batch.create_index("ix_resumes_profile_id", ["profile_id"], unique=False)
        batch.create_foreign_key(
            "fk_resumes_profile_id", "resume_profiles", ["profile_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("resumes") as batch:
        batch.drop_constraint("fk_resumes_profile_id", type_="foreignkey")
        batch.drop_index("ix_resumes_profile_id")
        batch.drop_column("profile_id")
    with op.batch_alter_table("kb_chunks") as batch:
        batch.drop_constraint("fk_kb_chunks_profile_id", type_="foreignkey")
        batch.drop_index("ix_kb_chunks_profile_id")
        batch.drop_column("profile_id")
    op.drop_table("resume_profiles")
