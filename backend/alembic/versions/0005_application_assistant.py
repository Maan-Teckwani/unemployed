"""application_assistant — provenance, browser state, and follow-up reminders

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("profile_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resume_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("application_url", sa.String(length=1000), nullable=False, server_default=""))
        batch.add_column(sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("assistant_state", sa.String(length=30), nullable=False, server_default="idle"))
        batch.create_foreign_key(
            "fk_applications_profile_id", "resume_profiles", ["profile_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_applications_resume_id", "resumes", ["resume_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_constraint("fk_applications_resume_id", type_="foreignkey")
        batch.drop_constraint("fk_applications_profile_id", type_="foreignkey")
        batch.drop_column("assistant_state")
        batch.drop_column("follow_up_at")
        batch.drop_column("application_url")
        batch.drop_column("resume_id")
        batch.drop_column("profile_id")
