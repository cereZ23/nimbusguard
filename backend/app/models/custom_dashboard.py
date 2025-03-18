from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class CustomDashboard(UUIDPrimaryKey, TimestampMixin, Base):
    """User-defined custom dashboard with configurable widget layout."""

    __tablename__ = "custom_dashboards"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # layout format: [
    #   {"widget": "secure_score", "x": 0, "y": 0, "w": 4, "h": 3, "config": {}},
    #   {"widget": "findings_by_severity", "x": 4, "y": 0, "w": 4, "h": 3, "config": {}},
    #   {"widget": "recent_findings", "x": 0, "y": 3, "w": 8, "h": 4, "config": {"limit": 10}},
    # ]
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
