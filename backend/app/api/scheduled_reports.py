from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.deps import DB, AdminUser, CurrentUser
from app.models.scheduled_report import ReportHistory, ScheduledReport
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.scheduled_report import (
    ReportHistoryResponse,
    ScheduledReportCreate,
    ScheduledReportResponse,
    ScheduledReportUpdate,
)
from app.services.report_scheduler import calculate_next_run

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_REPORT_TYPES = {"executive_summary", "compliance", "technical_detail"}
VALID_SCHEDULES = {"daily", "weekly", "monthly"}


@router.get("")
async def list_scheduled_reports(
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> ApiResponse[list[ScheduledReportResponse]]:
    """List all scheduled reports for the current tenant."""
    tenant_id = user.tenant_id

    total_q = await db.execute(
        select(func.count(ScheduledReport.id)).where(
            ScheduledReport.tenant_id == tenant_id
        )
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(ScheduledReport)
        .where(ScheduledReport.tenant_id == tenant_id)
        .order_by(ScheduledReport.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    reports = result.scalars().all()

    return ApiResponse(
        data=[
            ScheduledReportResponse.model_validate(r) for r in reports
        ],
        meta=PaginationMeta(total=total, page=page, size=size),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_scheduled_report(
    db: DB,
    user: AdminUser,
    payload: ScheduledReportCreate,
) -> ApiResponse[ScheduledReportResponse]:
    """Create a new scheduled report (admin only)."""
    if payload.report_type not in VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid report_type. Must be one of: {', '.join(VALID_REPORT_TYPES)}",
        )
    if payload.schedule not in VALID_SCHEDULES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid schedule. Must be one of: {', '.join(VALID_SCHEDULES)}",
        )

    next_run = calculate_next_run(payload.schedule)

    report = ScheduledReport(
        tenant_id=user.tenant_id,
        created_by=user.id,
        name=payload.name,
        report_type=payload.report_type,
        schedule=payload.schedule,
        config=payload.config,
        is_active=True,
        next_run_at=next_run,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info(
        "Scheduled report created: %s (type=%s, schedule=%s) for tenant %s",
        report.id,
        report.report_type,
        report.schedule,
        user.tenant_id,
    )

    return ApiResponse(
        data=ScheduledReportResponse.model_validate(report),
    )


# Static path routes MUST come before dynamic {report_id} routes
# to avoid "history" being matched as a report_id.


@router.get("/history/{history_id}/download")
async def download_report_history(
    history_id: str,
    db: DB,
    user: CurrentUser,
) -> FileResponse:
    """Download a generated report PDF."""
    result = await db.execute(
        select(ReportHistory).where(
            ReportHistory.id == history_id,
            ReportHistory.tenant_id == user.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report history entry not found",
        )

    if entry.status != "completed" or not entry.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file is not available",
        )

    if not os.path.exists(entry.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found on disk",
        )

    filename = os.path.basename(entry.file_path)
    return FileResponse(
        path=entry.file_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.put("/{report_id}")
async def update_scheduled_report(
    report_id: str,
    db: DB,
    user: AdminUser,
    payload: ScheduledReportUpdate,
) -> ApiResponse[ScheduledReportResponse]:
    """Update a scheduled report (admin only)."""
    result = await db.execute(
        select(ScheduledReport).where(
            ScheduledReport.id == report_id,
            ScheduledReport.tenant_id == user.tenant_id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled report not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "report_type" in update_data and update_data["report_type"] not in VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid report_type. Must be one of: {', '.join(VALID_REPORT_TYPES)}",
        )
    if "schedule" in update_data and update_data["schedule"] not in VALID_SCHEDULES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid schedule. Must be one of: {', '.join(VALID_SCHEDULES)}",
        )

    for field, value in update_data.items():
        setattr(report, field, value)

    # Recalculate next_run_at if schedule changed or report was re-activated
    if "schedule" in update_data or ("is_active" in update_data and update_data["is_active"]):
        report.next_run_at = calculate_next_run(report.schedule)

    # If deactivated, clear next_run_at
    if "is_active" in update_data and not update_data["is_active"]:
        report.next_run_at = None

    await db.commit()
    await db.refresh(report)

    logger.info("Scheduled report %s updated for tenant %s", report_id, user.tenant_id)

    return ApiResponse(
        data=ScheduledReportResponse.model_validate(report),
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_report(
    report_id: str,
    db: DB,
    user: AdminUser,
) -> None:
    """Delete a scheduled report (admin only)."""
    result = await db.execute(
        select(ScheduledReport).where(
            ScheduledReport.id == report_id,
            ScheduledReport.tenant_id == user.tenant_id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled report not found",
        )

    await db.delete(report)
    await db.commit()

    logger.info("Scheduled report %s deleted for tenant %s", report_id, user.tenant_id)


@router.get("/{report_id}/history")
async def list_report_history(
    report_id: str,
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> ApiResponse[list[ReportHistoryResponse]]:
    """List generated report history for a scheduled report."""
    # Verify the scheduled report belongs to this tenant
    sr_result = await db.execute(
        select(ScheduledReport.id).where(
            ScheduledReport.id == report_id,
            ScheduledReport.tenant_id == user.tenant_id,
        )
    )
    if sr_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled report not found",
        )

    total_q = await db.execute(
        select(func.count(ReportHistory.id)).where(
            ReportHistory.scheduled_report_id == report_id,
            ReportHistory.tenant_id == user.tenant_id,
        )
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(ReportHistory)
        .where(
            ReportHistory.scheduled_report_id == report_id,
            ReportHistory.tenant_id == user.tenant_id,
        )
        .order_by(ReportHistory.generated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    entries = result.scalars().all()

    return ApiResponse(
        data=[ReportHistoryResponse.model_validate(e) for e in entries],
        meta=PaginationMeta(total=total, page=page, size=size),
    )
