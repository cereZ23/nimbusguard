"""Audit log service — records user actions for compliance."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Insert an audit log entry."""
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        metadata_=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    logger.info(
        "Audit: %s by user=%s tenant=%s resource=%s/%s",
        action,
        user_id,
        tenant_id,
        resource_type,
        resource_id,
    )
    return entry
