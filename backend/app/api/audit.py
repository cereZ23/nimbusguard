from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminUser
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse
from app.schemas.common import ApiResponse, PaginationMeta

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ApiResponse[list[AuditLogResponse]])
async def list_audit_logs(
    db: DB,
    user: AdminUser,
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    tenant_id = user.tenant_id

    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate (eager-load user for user_email field)
    query = (
        query.options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    data = []
    for e in entries:
        resp = AuditLogResponse(
            id=str(e.id),
            tenant_id=str(e.tenant_id),
            user_id=str(e.user_id) if e.user_id else None,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            detail=e.detail,
            metadata=e.metadata_,
            ip_address=e.ip_address,
            created_at=e.created_at,
            user_email=e.user.email if e.user else None,
        )
        data.append(resp)

    return {
        "data": data,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }
