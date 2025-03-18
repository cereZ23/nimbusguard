from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Scan(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "scans"

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_type: Mapped[str] = mapped_column(String(20), default="full")  # full | incremental
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    cloud_account: Mapped[CloudAccount] = relationship(back_populates="scans", lazy="noload")
    findings: Mapped[list[Finding]] = relationship(back_populates="scan", lazy="noload")


from app.models.cloud_account import CloudAccount  # noqa: E402
from app.models.finding import Finding  # noqa: E402
