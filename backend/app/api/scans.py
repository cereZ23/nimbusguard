from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.deps import DB, AdminUser, CurrentUser
from app.exceptions import ConflictError
from app.models.cloud_account import CloudAccount
from app.models.scan import Scan
from app.rate_limit import limiter
from app.schemas.common import ApiResponse
from app.schemas.scans import ScanCreate, ScanResponse
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ApiResponse[ScanResponse], status_code=status.HTTP_201_CREATED)
@limiter.limit("60/hour")
async def create_scan(request: Request, body: ScanCreate, db: DB, user: AdminUser) -> dict:
    # Verify account belongs to tenant
    account = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == body.cloud_account_id,
            CloudAccount.tenant_id == user.tenant_id,
        )
    )
    if account.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Check no scan already running
    running = await db.execute(
        select(Scan).where(
            Scan.cloud_account_id == body.cloud_account_id,
            Scan.status.in_(["pending", "running"]),
        )
    )
    if running.scalar_one_or_none():
        raise ConflictError("A scan is already in progress for this account")

    scan = Scan(
        cloud_account_id=body.cloud_account_id,
        scan_type=body.scan_type,
        status="pending",
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="scan.trigger",
        resource_type="scan",
        resource_id=str(scan.id),
        detail=f"Scan triggered for account {body.cloud_account_id}",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    # Dispatch Celery task
    from app.worker.tasks import run_scan

    run_scan.delay(str(scan.id))

    logger.info("Scan created: %s for account %s", scan.id, body.cloud_account_id)
    return {"data": scan, "error": None, "meta": None}


@router.get("/{scan_id}", response_model=ApiResponse[ScanResponse])
async def get_scan(scan_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    result = await db.execute(
        select(Scan).join(CloudAccount).where(Scan.id == scan_id, CloudAccount.tenant_id == user.tenant_id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return {"data": scan, "error": None, "meta": None}
