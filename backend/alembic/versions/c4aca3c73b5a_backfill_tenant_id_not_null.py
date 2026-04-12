"""Backfill tenant_id on findings + assets, then make NOT NULL.

The tenant_id columns were added in migration d4e5f6a7b8c9 as nullable
with a "backfill later" comment. The evaluator and collector never
populated them — all rows have tenant_id = NULL. This migration:

1. Backfills tenant_id from the cloud_accounts JOIN.
2. Makes both columns NOT NULL so future inserts without tenant_id fail
   loudly instead of silently creating orphan rows.

Revision ID: c4aca3c73b5a
Revises: f6a7b8c9d0e1
Create Date: 2026-04-12 14:10:20.279565
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c4aca3c73b5a"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: backfill from cloud_accounts
    op.execute(
        """
        UPDATE findings
        SET tenant_id = ca.tenant_id
        FROM cloud_accounts ca
        WHERE findings.cloud_account_id = ca.id
          AND findings.tenant_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE assets
        SET tenant_id = ca.tenant_id
        FROM cloud_accounts ca
        WHERE assets.cloud_account_id = ca.id
          AND assets.tenant_id IS NULL
        """
    )

    # Step 2: make NOT NULL
    op.alter_column("findings", "tenant_id", nullable=False)
    op.alter_column("assets", "tenant_id", nullable=False)


def downgrade() -> None:
    op.alter_column("findings", "tenant_id", nullable=True)
    op.alter_column("assets", "tenant_id", nullable=True)
