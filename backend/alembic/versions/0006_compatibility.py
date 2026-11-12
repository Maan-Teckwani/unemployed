"""Compatibility bridge for the privacy/settings migration chain.

The branch already contains revisions 0007 and 0008 which reference 0006.
Feature tables are intentionally created by 0009, after the latest existing
revision, so this bridge does not change application data.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
