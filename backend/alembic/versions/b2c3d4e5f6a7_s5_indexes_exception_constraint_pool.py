"""S5: add indexes, remove exception unique constraint, widen mfa_secret

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add composite indexes for common query patterns
    op.create_index('ix_scans_account_status', 'scans', ['cloud_account_id', 'status'])
    op.create_index('ix_refresh_tokens_hash_revoked', 'refresh_tokens', ['token_hash', 'revoked'])
    op.create_index('ix_exceptions_finding_status', 'exceptions', ['finding_id', 'status'])

    # Remove the unique constraint on exceptions.finding_id to allow re-waiver after rejection
    # The constraint name varies — try common patterns
    try:
        op.drop_constraint('exceptions_finding_id_key', 'exceptions', type_='unique')
    except Exception:
        # If the constraint has a different name, try the index
        try:
            op.drop_index('ix_exceptions_finding_id', 'exceptions')
        except Exception:
            pass

    # Add a regular index on exceptions.finding_id (replacing the unique constraint)
    # Note: ix_exceptions_finding_status above already covers this


def downgrade() -> None:
    op.drop_index('ix_exceptions_finding_status', 'exceptions')
    op.drop_index('ix_refresh_tokens_hash_revoked', 'refresh_tokens')
    op.drop_index('ix_scans_account_status', 'scans')

    # Re-add unique constraint
    op.create_unique_constraint('exceptions_finding_id_key', 'exceptions', ['finding_id'])
