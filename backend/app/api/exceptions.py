from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser, CurrentUser
from app.models.cloud_account import CloudAccount
from app.models.exception import Exception_
from app.models.finding import Finding
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.exceptions import ExceptionCreateRequest, ExceptionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/findings/{finding_id}/exception",
    response_model=ApiResponse[ExceptionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_exception(
    finding_id: uuid.UUID, body: ExceptionCreateRequest, db: DB, user: CurrentUser
) -> dict:
    # Verify finding belongs to tenant
    result = await db.execute(
        select(Finding)
        .join(CloudAccount)
        .where(Finding.id == finding_id, CloudAccount.tenant_id == user.tenant_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    # Check no existing active exception
    existing = await db.execute(
        select(Exception_).where(
            Exception_.finding_id == finding_id,
            Exception_.status.in_(["requested", "approved"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active exception already exists for this finding",
        )

    exc = Exception_(
        finding_id=finding_id,
        reason=body.reason,
        status="requested",
        expires_at=body.expires_at,
    )
    db.add(exc)
    await db.commit()
    await db.refresh(exc)

    logger.info("Exception requested for finding %s by %s", finding_id, user.email)
    return {"data": exc, "error": None, "meta": None}


@router.get("/exceptions", response_model=ApiResponse[list[ExceptionResponse]])
async def list_exceptions(
    db: DB,
    user: CurrentUser,
    exc_status: str | None = Query(None, alias="status"),
    page: int = 1,
    size: int = 20,
) -> dict:
    base = (
        select(Exception_)
        .join(Finding, Finding.id == Exception_.finding_id)
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(CloudAccount.tenant_id == user.tenant_id)
    )
    count_base = (
        select(func.count(Exception_.id))
        .join(Finding, Finding.id == Exception_.finding_id)
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(CloudAccount.tenant_id == user.tenant_id)
    )

    if exc_status:
        base = base.where(Exception_.status == exc_status)
        count_base = count_base.where(Exception_.status == exc_status)

    total = (await db.execute(count_base)).scalar() or 0
    result = await db.execute(
        base.order_by(Exception_.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    exceptions = result.scalars().all()

    return {
        "data": exceptions,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.put(
    "/exceptions/{exception_id}/approve",
    response_model=ApiResponse[ExceptionResponse],
)
async def approve_exception(
    exception_id: uuid.UUID, db: DB, user: AdminUser
) -> dict:
    result = await db.execute(
        select(Exception_)
        .join(Finding, Finding.id == Exception_.finding_id)
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(Exception_.id == exception_id, CloudAccount.tenant_id == user.tenant_id)
    )
    exc = result.scalar_one_or_none()
    if exc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

    if exc.status != "requested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve exception in status '{exc.status}'",
        )

    exc.status = "approved"
    exc.approved_by = user.email

    # Mark finding as waived
    finding = await db.execute(select(Finding).where(Finding.id == exc.finding_id))
    finding_obj = finding.scalar_one()
    finding_obj.waived = True

    await db.commit()
    await db.refresh(exc)

    logger.info("Exception %s approved by %s", exception_id, user.email)
    return {"data": exc, "error": None, "meta": None}


@router.put(
    "/exceptions/{exception_id}/reject",
    response_model=ApiResponse[ExceptionResponse],
)
async def reject_exception(
    exception_id: uuid.UUID, db: DB, user: AdminUser
) -> dict:
    result = await db.execute(
        select(Exception_)
        .join(Finding, Finding.id == Exception_.finding_id)
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(Exception_.id == exception_id, CloudAccount.tenant_id == user.tenant_id)
    )
    exc = result.scalar_one_or_none()
    if exc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

    if exc.status != "requested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject exception in status '{exc.status}'",
        )

    exc.status = "rejected"
    await db.commit()
    await db.refresh(exc)

    logger.info("Exception %s rejected by %s", exception_id, user.email)
    return {"data": exc, "error": None, "meta": None}

