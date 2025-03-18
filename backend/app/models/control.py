from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Control(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "controls"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # e.g. CIS-AZ-01
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # high | medium | low
    framework: Mapped[str] = mapped_column(String(50), default="cis-lite")
    remediation_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Map to provider-specific check references
    # e.g. {"azure": "assessment-id", "aws": "config-rule-arn"}
    provider_check_ref: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    # Multi-framework compliance mappings
    # e.g. {"soc2": ["CC6.1", "CC6.6"], "nist": ["AC-2", "AC-3"]}
    framework_mappings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    findings: Mapped[list[Finding]] = relationship(back_populates="control", lazy="noload")


from app.models.finding import Finding  # noqa: E402
