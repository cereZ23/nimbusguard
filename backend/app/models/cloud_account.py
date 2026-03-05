from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class CloudAccount(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "cloud_accounts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # azure | aws
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Azure: subscription_id; AWS: account_id
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_ref: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | error | disabled
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_schedule: Mapped[str | None] = mapped_column(String(50), nullable=True)  # cron expression

    tenant: Mapped[Tenant] = relationship(back_populates="cloud_accounts", lazy="noload")
    assets: Mapped[list[Asset]] = relationship(back_populates="cloud_account", lazy="noload")
    scans: Mapped[list[Scan]] = relationship(back_populates="cloud_account", lazy="noload")


from app.models.asset import Asset  # noqa: E402
from app.models.scan import Scan  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
