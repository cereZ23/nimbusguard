from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class ComplianceSnapshot(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "compliance_snapshots"
    __table_args__ = (
        Index(
            "ix_compliance_snapshot_tenant_date",
            "tenant_id",
            "framework",
            "snapshot_date",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    total_controls: Mapped[int] = mapped_column(Integer, nullable=False)
    passing_controls: Mapped[int] = mapped_column(Integer, nullable=False)
    failing_controls: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    cloud_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cloud_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
