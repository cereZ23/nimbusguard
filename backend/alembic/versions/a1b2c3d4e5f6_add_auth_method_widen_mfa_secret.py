"""add auth_method column and widen mfa_secret for Fernet encryption

Revision ID: a1b2c3d4e5f6
Revises: 0b1a7574522d
Create Date: 2026-03-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0b1a7574522d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auth_method column (password/sso/scim) with default "password"
    op.add_column('users', sa.Column('auth_method', sa.String(20), nullable=False, server_default='password'))

    # Widen mfa_secret from String(32) to String(500) to fit Fernet-encrypted values
    op.alter_column('users', 'mfa_secret',
                    existing_type=sa.String(32),
                    type_=sa.String(500),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'mfa_secret',
                    existing_type=sa.String(500),
                    type_=sa.String(32),
                    existing_nullable=True)
    op.drop_column('users', 'auth_method')
