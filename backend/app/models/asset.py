from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Asset(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_provider_id", "provider_id"),
        Index("ix_assets_cloud_account_type", "cloud_account_id", "resource_type"),
    )

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(String(1024), nullable=False)  # ARM id or ARN
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    raw_properties: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cloud_account: Mapped[CloudAccount] = relationship(back_populates="assets", lazy="noload")
    findings: Mapped[list[Finding]] = relationship(back_populates="asset", lazy="noload")


from app.models.cloud_account import CloudAccount  # noqa: E402
from app.models.finding import Finding  # noqa: E402
