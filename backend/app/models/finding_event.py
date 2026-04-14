from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class FindingEvent(UUIDPrimaryKey, TimestampMixin, Base):
    """Timeline event for a finding — tracks status changes, assignments, comments, etc."""

    __tablename__ = "finding_events"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # status_change, severity_change, assigned, unassigned, commented, waiver_requested, waiver_approved
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    finding = relationship("Finding", back_populates="events", lazy="noload")
    user = relationship("User", lazy="noload")
