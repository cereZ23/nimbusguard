"""add priority layer fields to findings and controls

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-10 23:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── controls: metadata used by the priority calculator ───────────
    op.add_column(
        "controls",
        sa.Column("effort", sa.String(16), nullable=True),
    )
    op.add_column(
        "controls",
        sa.Column("exposure", sa.String(16), nullable=True),
    )
    op.add_column(
        "controls",
        sa.Column("remediation_group", sa.String(100), nullable=True),
    )
    op.add_column(
        "controls",
        sa.Column("remediation_action", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_controls_remediation_group",
        "controls",
        ["remediation_group"],
    )

    # ── findings: calculated priority bucket and sorting score ──────
    op.add_column(
        "findings",
        sa.Column("priority", sa.String(4), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("priority_score", sa.Integer(), nullable=True),
    )
    op.create_index("ix_findings_priority", "findings", ["priority"])
    op.create_index(
        "ix_findings_priority_score",
        "findings",
        [sa.text("priority_score DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_findings_priority_score", table_name="findings")
    op.drop_index("ix_findings_priority", table_name="findings")
    op.drop_column("findings", "priority_score")
    op.drop_column("findings", "priority")

    op.drop_index("ix_controls_remediation_group", table_name="controls")
    op.drop_column("controls", "remediation_action")
    op.drop_column("controls", "remediation_group")
    op.drop_column("controls", "exposure")
    op.drop_column("controls", "effort")
