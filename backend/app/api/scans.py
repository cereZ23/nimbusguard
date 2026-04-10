from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser, CurrentUser
from app.exceptions import ConflictError
from app.models.cloud_account import CloudAccount
from app.models.finding import Finding
from app.models.scan import Scan
from app.rate_limit import limiter
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.scans import ScanCreate, ScanResponse
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


def _compute_duration(scan: Scan) -> int | None:
    """Return duration in integer seconds between started_at and finished_at."""
    if scan.started_at is None:
        return None
    end = scan.finished_at or datetime.now(scan.started_at.tzinfo)
    delta = end - scan.started_at
    return int(delta.total_seconds())


async def _findings_counts(
    db: DB,
    scan_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, int]]:
    """Aggregate pass/fail/total counts for a batch of scans in one query.

    Returns a dict keyed by scan_id with keys: total, pass, fail.
    Missing scan_ids get zeros by default.
    """
    if not scan_ids:
        return {}
    result = await db.execute(
        select(
            Finding.scan_id,
            Finding.status,
            func.count(Finding.id).label("count"),
        )
        .where(Finding.scan_id.in_(scan_ids))
        .group_by(Finding.scan_id, Finding.status)
    )
    counts: dict[uuid.UUID, dict[str, int]] = {}
    for scan_id, status_value, count in result.all():
        bucket = counts.setdefault(scan_id, {"total": 0, "pass": 0, "fail": 0})
        bucket["total"] += count
        if status_value in bucket:
            bucket[status_value] += count
    return counts


def _scan_to_response(
    scan: Scan,
    *,
    account: CloudAccount | None,
    counts: dict[str, int] | None,
) -> dict:
    """Build a ScanResponse-shaped dict enriched with account info and counts."""
    counts = counts or {"total": 0, "pass": 0, "fail": 0}
    return {
        "id": scan.id,
        "cloud_account_id": scan.cloud_account_id,
        "cloud_account_name": account.display_name if account is not None else None,
        "cloud_account_provider": account.provider if account is not None else None,
        "scan_type": scan.scan_type,
        "status": scan.status,
        "started_at": scan.started_at,
        "finished_at": scan.finished_at,
        "stats": scan.stats,
        "created_at": scan.created_at,
        "duration_seconds": _compute_duration(scan),
        "findings_count": counts.get("total", 0),
        "findings_fail_count": counts.get("fail", 0),
        "findings_pass_count": counts.get("pass", 0),
    }


@router.post("", response_model=ApiResponse[ScanResponse], status_code=status.HTTP_201_CREATED)
@limiter.limit("60/hour")
async def create_scan(request: Request, body: ScanCreate, db: DB, user: AdminUser) -> dict:
    # Verify account belongs to tenant.
    account = (
        await db.execute(
            select(CloudAccount).where(
                CloudAccount.id == body.cloud_account_id,
                CloudAccount.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Check no scan already running.
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
    await db.flush()

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
    await db.refresh(scan)

    # Dispatch Celery task.
    from app.worker.tasks import run_scan

    run_scan.delay(str(scan.id))

    logger.info("Scan created: %s for account %s", scan.id, body.cloud_account_id)
    return {
        "data": _scan_to_response(scan, account=account, counts=None),
        "error": None,
        "meta": None,
    }


@router.get("", response_model=ApiResponse[list[ScanResponse]])
async def list_scans(
    db: DB,
    user: CurrentUser,
    cloud_account_id: uuid.UUID | None = Query(None, description="Filter by cloud account"),
    status: str | None = Query(None, description="Filter by status: pending|running|completed|failed"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    """List scans for the current tenant, newest first.

    Tenant isolation enforced via JOIN on cloud_accounts.tenant_id.
    """
    base = select(Scan).join(CloudAccount, Scan.cloud_account_id == CloudAccount.id).where(
        CloudAccount.tenant_id == user.tenant_id
    )
    count_base = select(func.count(Scan.id)).join(
        CloudAccount, Scan.cloud_account_id == CloudAccount.id
    ).where(CloudAccount.tenant_id == user.tenant_id)

    if cloud_account_id is not None:
        base = base.where(Scan.cloud_account_id == cloud_account_id)
        count_base = count_base.where(Scan.cloud_account_id == cloud_account_id)

    if status is not None:
        base = base.where(Scan.status == status)
        count_base = count_base.where(Scan.status == status)

    total = (await db.execute(count_base)).scalar() or 0

    rows_result = await db.execute(
        base.order_by(Scan.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    scans = list(rows_result.scalars().all())

    # Batch-load related cloud accounts in a single query.
    account_ids = list({scan.cloud_account_id for scan in scans})
    accounts_by_id: dict[uuid.UUID, CloudAccount] = {}
    if account_ids:
        accounts_result = await db.execute(
            select(CloudAccount).where(CloudAccount.id.in_(account_ids))
        )
        for acc in accounts_result.scalars().all():
            accounts_by_id[acc.id] = acc

    # Batch-load findings counts in a single aggregate query.
    scan_ids = [scan.id for scan in scans]
    counts_by_scan = await _findings_counts(db, scan_ids)

    data = [
        _scan_to_response(
            scan,
            account=accounts_by_id.get(scan.cloud_account_id),
            counts=counts_by_scan.get(scan.id),
        )
        for scan in scans
    ]

    return {
        "data": data,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.get("/{scan_id}", response_model=ApiResponse[ScanResponse])
async def get_scan(scan_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    result = await db.execute(
        select(Scan, CloudAccount)
        .join(CloudAccount, Scan.cloud_account_id == CloudAccount.id)
        .where(Scan.id == scan_id, CloudAccount.tenant_id == user.tenant_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    scan, account = row
    counts_by_scan = await _findings_counts(db, [scan.id])
    return {
        "data": _scan_to_response(
            scan,
            account=account,
            counts=counts_by_scan.get(scan.id),
        ),
        "error": None,
        "meta": None,
    }
