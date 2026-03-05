from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Tenant(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    branding: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)

    users: Mapped[list[User]] = relationship(back_populates="tenant", lazy="noload")
    cloud_accounts: Mapped[list[CloudAccount]] = relationship(back_populates="tenant", lazy="noload")


# Avoid circular imports — resolved at module level
from app.models.cloud_account import CloudAccount  # noqa: E402
from app.models.user import User  # noqa: E402
