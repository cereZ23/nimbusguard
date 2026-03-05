from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class AssetRelationship(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "relationship_type",
            name="uq_asset_rel_src_tgt_type",
        ),
    )

    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # contains, uses, attached_to, routes_to, protects, member_of
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    source_asset: Mapped[Asset] = relationship(foreign_keys=[source_asset_id], lazy="noload")
    target_asset: Mapped[Asset] = relationship(foreign_keys=[target_asset_id], lazy="noload")


from app.models.asset import Asset  # noqa: E402
