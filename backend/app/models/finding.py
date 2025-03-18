from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Finding(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_dedup", "dedup_key", unique=True),
        Index("ix_findings_account_control", "cloud_account_id", "control_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_status", "status"),
        Index("ix_findings_account_status", "cloud_account_id", "status"),
        Index("ix_findings_last_evaluated", "last_evaluated_at"),
    )

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    control_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("controls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pass|fail|error|not_applicable
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # high|medium|low
    dedup_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="")
    jira_ticket_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    jira_ticket_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    waived: Mapped[bool] = mapped_column(default=False)
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped[Asset | None] = relationship(back_populates="findings", lazy="noload")
    control: Mapped[Control | None] = relationship(back_populates="findings", lazy="noload")
    scan: Mapped[Scan | None] = relationship(back_populates="findings", lazy="noload")
    evidences: Mapped[list[Evidence]] = relationship(back_populates="finding", lazy="noload")
    remediation: Mapped[Remediation | None] = relationship(
        back_populates="finding", uselist=False, lazy="noload"
    )
    exception: Mapped[Exception_ | None] = relationship(
        back_populates="finding", uselist=False, lazy="noload"
    )
    assignee: Mapped[User | None] = relationship(
        "User", foreign_keys=[assigned_to], lazy="noload"
    )
    comments: Mapped[list[FindingComment]] = relationship(
        back_populates="finding", cascade="all, delete-orphan", lazy="noload"
    )
    events: Mapped[list[FindingEvent]] = relationship(
        back_populates="finding", cascade="all, delete-orphan", lazy="noload"
    )


from app.models.asset import Asset  # noqa: E402
from app.models.control import Control  # noqa: E402
from app.models.scan import Scan  # noqa: E402
from app.models.evidence import Evidence  # noqa: E402
from app.models.remediation import Remediation  # noqa: E402
from app.models.exception import Exception_  # noqa: E402
from app.models.finding_comment import FindingComment  # noqa: E402
from app.models.finding_event import FindingEvent  # noqa: E402
from app.models.user import User  # noqa: E402
