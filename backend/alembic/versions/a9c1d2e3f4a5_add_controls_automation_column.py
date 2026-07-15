"""add automation column to controls

Revision ID: a9c1d2e3f4a5
Revises: c4aca3c73b5a
Create Date: 2026-07-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9c1d2e3f4a5"
down_revision: Union[str, None] = "c4aca3c73b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # "automated" (default) | "manual" — manual controls have no app-only
    # API (e.g. Teams admin policies) and never produce findings.
    op.add_column(
        "controls",
        sa.Column("automation", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("controls", "automation")
