"""denormalize tenant_id on findings/assets, CHECK constraints, missing indexes, unique constraint

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Denormalize tenant_id onto findings and assets --
    op.add_column(
        "findings",
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_findings_tenant_id", "findings", ["tenant_id"])

    op.add_column(
        "assets",
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_assets_tenant_id", "assets", ["tenant_id"])

    # -- Composite indexes for common query patterns --
    op.create_index("ix_findings_tenant_status_severity", "findings", ["tenant_id", "status", "severity"])
    op.create_index("ix_assets_tenant_resource_type", "assets", ["tenant_id", "resource_type"])

    # -- CHECK constraints on status/severity enums --
    op.create_check_constraint(
        "ck_findings_status",
        "findings",
        "status IN ('pass', 'fail', 'error', 'not_applicable')",
    )
    op.create_check_constraint(
        "ck_findings_severity",
        "findings",
        "severity IN ('critical', 'high', 'medium', 'low')",
    )
    op.create_check_constraint(
        "ck_scans_status",
        "scans",
        "status IN ('pending', 'running', 'completed', 'failed')",
    )
    op.create_check_constraint(
        "ck_cloud_accounts_status",
        "cloud_accounts",
        "status IN ('active', 'error', 'disabled')",
    )

    # -- Missing indexes --
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_scans_finished_at", "scans", ["finished_at"])

    # -- Unique constraint: one provider account per tenant --
    op.create_unique_constraint(
        "uq_cloud_accounts_tenant_provider",
        "cloud_accounts",
        ["tenant_id", "provider_account_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_cloud_accounts_tenant_provider", "cloud_accounts", type_="unique")

    op.drop_index("ix_scans_finished_at", table_name="scans")
    op.drop_index("ix_findings_scan_id", table_name="findings")

    op.drop_constraint("ck_cloud_accounts_status", "cloud_accounts", type_="check")
    op.drop_constraint("ck_scans_status", "scans", type_="check")
    op.drop_constraint("ck_findings_severity", "findings", type_="check")
    op.drop_constraint("ck_findings_status", "findings", type_="check")

    op.drop_index("ix_assets_tenant_resource_type", table_name="assets")
    op.drop_index("ix_findings_tenant_status_severity", table_name="findings")

    op.drop_index("ix_assets_tenant_id", table_name="assets")
    op.drop_column("assets", "tenant_id")

    op.drop_index("ix_findings_tenant_id", table_name="findings")
    op.drop_column("findings", "tenant_id")
