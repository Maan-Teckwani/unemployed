"""applications.applied_at — when it was sent, recorded once

The home page shows a pile of everything you have sent, and that number must
never fall. It cannot be derived from `status`, because a rejection changes the
status without un-sending the application, and it cannot be derived from
`updated_at`, because that moves every time the row is touched.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A nullable ADD COLUMN is native on SQLite, so this needs no batch rebuild
    # even though alembic/env.py enables render_as_batch for the cases that do.
    op.add_column(
        "applications",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill, or everyone who already uses this app opens it to a pile of zero
    # and a counter that says today is their first day.
    #
    # `updated_at` is an approximation — it has moved for anyone who changed a
    # row after applying — but it is the only evidence that exists, and it is
    # exactly right for the rows nobody has touched since.
    #
    # `closed` is deliberately left out. A closed job may have been applied to
    # and rejected, or closed without ever being sent, and nothing stored here
    # tells the two apart. Undercounting an old pile is the kinder error:
    # inventing applications somebody never sent is worse than missing a few,
    # and every application from here on is recorded exactly.
    op.execute(
        "UPDATE applications SET applied_at = updated_at "
        "WHERE status IN ('applied', 'outreach_sent')"
    )


def downgrade() -> None:
    op.drop_column("applications", "applied_at")
