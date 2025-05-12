from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminUser, CurrentUser
from app.models.cloud_account import CloudAccount
from app.models.exception import Exception_
from app.models.finding import Finding
from app.models.finding_comment import FindingComment
from app.models.finding_event import FindingEvent
from app.models.user import User
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.finding_event import FindingEventResponse
from app.config.remediation_snippets import get_remediation_for_control
from app.schemas.findings import (
    AssignRequest,
    BulkWaiveRequest,
    BulkWaiveResult,
    CommentCreate,
    CommentResponse,
    FindingDetail,
    FindingResponse,
    RemediationResponse,
    RemediationSnippets,
    SimilarFindingResponse,
)
from app.services.audit import record_audit
from app.services.finding_timeline import record_event

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────


def _finding_response_with_assignee(finding: Finding) -> dict:
    """Build a dict suitable for FindingResponse, enriching assignee info if loaded."""
    data = {
        "id": finding.id,
        "status": finding.status,
        "severity": finding.severity,
        "title": finding.title,
        "dedup_key": finding.dedup_key,
        "waived": finding.waived,
        "first_detected_at": finding.first_detected_at,
        "last_evaluated_at": finding.last_evaluated_at,
        "cloud_account_id": finding.cloud_account_id,
        "asset_id": finding.asset_id,
        "control_id": finding.control_id,
        "scan_id": finding.scan_id,
        "assigned_to": finding.assigned_to,
        "assignee_email": None,
        "assignee_name": None,
    }
    if finding.assigned_to and finding.assignee:
        data["assignee_email"] = finding.assignee.email
        data["assignee_name"] = finding.assignee.full_name
    return data


def _finding_detail_with_assignee(finding: Finding) -> dict:
    """Build a dict for FindingDetail with assignee info."""
    data = _finding_response_with_assignee(finding)
    data["asset"] = finding.asset
    data["control"] = finding.control
    data["evidences"] = finding.evidences
    return data


async def _get_tenant_finding(
    db: DB, finding_id: uuid.UUID, tenant_id: uuid.UUID
) -> Finding:
    """Fetch a finding ensuring it belongs to the given tenant."""
    result = await db.execute(
        select(Finding)
        .join(CloudAccount)
        .where(Finding.id == finding_id, CloudAccount.tenant_id == tenant_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    return finding


# ── List findings ────────────────────────────────────────────────────


@router.get("", response_model=ApiResponse[list[FindingResponse]])
async def list_findings(
    db: DB,
    user: CurrentUser,
    page: int = 1,
    size: int = 20,
    severity: str | None = Query(None),
    finding_status: str | None = Query(None, alias="status"),
    account_id: uuid.UUID | None = Query(None),
    asset_id: uuid.UUID | None = Query(None),
    control_id: uuid.UUID | None = Query(None),
    assigned_to: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sort_by: str = Query(
        "last_evaluated_at",
        pattern=r"^(title|severity|status|first_detected_at|last_evaluated_at)$",
    ),
    sort_order: str = Query("desc", pattern=r"^(asc|desc)$"),
) -> dict:
    base = (
        select(Finding)
        .join(CloudAccount)
        .where(CloudAccount.tenant_id == user.tenant_id)
        .options(selectinload(Finding.assignee))
    )
    count_base = (
        select(func.count(Finding.id))
        .join(CloudAccount)
        .where(CloudAccount.tenant_id == user.tenant_id)
    )

    if search:
        like = f"%{search}%"
        base = base.where(Finding.title.ilike(like))
        count_base = count_base.where(Finding.title.ilike(like))
    if severity:
        base = base.where(Finding.severity == severity)
        count_base = count_base.where(Finding.severity == severity)
    if finding_status:
        base = base.where(Finding.status == finding_status)
        count_base = count_base.where(Finding.status == finding_status)
    if account_id:
        base = base.where(Finding.cloud_account_id == account_id)
        count_base = count_base.where(Finding.cloud_account_id == account_id)
    if asset_id:
        base = base.where(Finding.asset_id == asset_id)
        count_base = count_base.where(Finding.asset_id == asset_id)
    if control_id:
        base = base.where(Finding.control_id == control_id)
        count_base = count_base.where(Finding.control_id == control_id)
    if assigned_to:
        base = base.where(Finding.assigned_to == assigned_to)
        count_base = count_base.where(Finding.assigned_to == assigned_to)
    if date_from:
        dt_from = datetime.fromisoformat(date_from)
        base = base.where(Finding.first_detected_at >= dt_from)
        count_base = count_base.where(Finding.first_detected_at >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to)
        base = base.where(Finding.first_detected_at <= dt_to)
        count_base = count_base.where(Finding.first_detected_at <= dt_to)

    total = (await db.execute(count_base)).scalar() or 0

    sort_col = getattr(Finding, sort_by)
    order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
    result = await db.execute(
        base.order_by(order).offset((page - 1) * size).limit(size)
    )
    findings = result.scalars().all()

    return {
        "data": [_finding_response_with_assignee(f) for f in findings],
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


# ── Get finding detail ──────────────────────────────────────────────


@router.get("/{finding_id}", response_model=ApiResponse[FindingDetail])
async def get_finding(finding_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    result = await db.execute(
        select(Finding)
        .join(CloudAccount)
        .where(Finding.id == finding_id, CloudAccount.tenant_id == user.tenant_id)
        .options(
            selectinload(Finding.asset),
            selectinload(Finding.control),
            selectinload(Finding.evidences),
            selectinload(Finding.assignee),
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    return {"data": _finding_detail_with_assignee(finding), "error": None, "meta": None}


# ── Remediation snippets ────────────────────────────────────────────


@router.get(
    "/{finding_id}/remediation",
    response_model=ApiResponse[RemediationResponse],
)
async def get_finding_remediation(
    finding_id: uuid.UUID, db: DB, user: CurrentUser
) -> dict:
    """Return IaC remediation snippets (Terraform, Bicep, Azure CLI) for a finding's control."""
    from app.models.control import Control

    result = await db.execute(
        select(Finding)
        .join(CloudAccount)
        .where(Finding.id == finding_id, CloudAccount.tenant_id == user.tenant_id)
        .options(selectinload(Finding.control))
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    control: Control | None = finding.control
    if control is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No control associated with this finding",
        )

    snippets_data = get_remediation_for_control(control.code)

    remediation = RemediationResponse(
        control_code=control.code,
        control_name=control.name,
        description=snippets_data.get("description") if snippets_data else None,
        remediation_hint=control.remediation_hint,
        snippets=RemediationSnippets(
            terraform=snippets_data.get("terraform") if snippets_data else None,
            bicep=snippets_data.get("bicep") if snippets_data else None,
            azure_cli=snippets_data.get("azure_cli") if snippets_data else None,
        ),
    )

    logger.info(
        "Remediation snippets requested for finding %s (control %s)",
        finding_id,
        control.code,
    )
    return {"data": remediation, "error": None, "meta": None}


# ── Similar findings ────────────────────────────────────────────────


@router.get(
    "/{finding_id}/similar",
    response_model=ApiResponse[list[SimilarFindingResponse]],
)
async def get_similar_findings(
    finding_id: uuid.UUID, db: DB, user: CurrentUser
) -> dict:
    """Return up to 10 similar findings: same control on other assets, or same asset with other controls."""
    # Validate that the finding belongs to the tenant
    result = await db.execute(
        select(Finding)
        .join(CloudAccount)
        .where(Finding.id == finding_id, CloudAccount.tenant_id == user.tenant_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    similar: list[SimilarFindingResponse] = []

    # 1. Same control, different asset (up to 7)
    if finding.control_id is not None:
        same_control_q = (
            select(Finding)
            .join(CloudAccount)
            .where(
                CloudAccount.tenant_id == user.tenant_id,
                Finding.control_id == finding.control_id,
                Finding.id != finding.id,
                Finding.asset_id != finding.asset_id,
                Finding.asset_id.isnot(None),
            )
            .options(
                selectinload(Finding.asset),
                selectinload(Finding.control),
            )
            .order_by(Finding.last_evaluated_at.desc())
            .limit(7)
        )
        sc_result = await db.execute(same_control_q)
        for f in sc_result.scalars().all():
            if f.asset is None or f.control is None:
                continue
            similar.append(
                SimilarFindingResponse(
                    id=f.id,
                    severity=f.severity,
                    status=f.status,
                    asset_name=f.asset.name,
                    asset_id=f.asset.id,
                    control_code=f.control.code,
                    control_name=f.control.name,
                    similarity_type="same_control",
                    first_detected_at=f.first_detected_at,
                )
            )

    # 2. Same asset, different control (fill up to 10 total)
    remaining = 10 - len(similar)
    if remaining > 0 and finding.asset_id is not None:
        same_asset_q = (
            select(Finding)
            .join(CloudAccount)
            .where(
                CloudAccount.tenant_id == user.tenant_id,
                Finding.asset_id == finding.asset_id,
                Finding.id != finding.id,
                Finding.control_id != finding.control_id,
                Finding.control_id.isnot(None),
            )
            .options(
                selectinload(Finding.asset),
                selectinload(Finding.control),
            )
            .order_by(Finding.last_evaluated_at.desc())
            .limit(remaining)
        )
        sa_result = await db.execute(same_asset_q)
        for f in sa_result.scalars().all():
            if f.asset is None or f.control is None:
                continue
            similar.append(
                SimilarFindingResponse(
                    id=f.id,
                    severity=f.severity,
                    status=f.status,
                    asset_name=f.asset.name,
                    asset_id=f.asset.id,
                    control_code=f.control.code,
                    control_name=f.control.name,
                    similarity_type="same_asset",
                    first_detected_at=f.first_detected_at,
                )
            )

    logger.info(
        "Found %d similar findings for finding %s", len(similar), finding_id
    )
    return {"data": similar, "error": None, "meta": None}


# ── Assign finding ──────────────────────────────────────────────────


@router.put("/{finding_id}/assign", response_model=ApiResponse[FindingResponse])
async def assign_finding(
    finding_id: uuid.UUID, body: AssignRequest, db: DB, user: CurrentUser
) -> dict:
    finding = await _get_tenant_finding(db, finding_id, user.tenant_id)

    if body.user_id is not None:
        # Validate assignee belongs to the same tenant
        assignee_result = await db.execute(
            select(User).where(
                User.id == body.user_id,
                User.tenant_id == user.tenant_id,
                User.is_active.is_(True),
            )
        )
        assignee = assignee_result.scalar_one_or_none()
        if assignee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignee not found or not in your tenant",
            )

    previous_assignee = finding.assigned_to
    finding.assigned_to = body.user_id

    # Record timeline event
    event_type = "assigned" if body.user_id else "unassigned"
    await record_event(
        db,
        finding_id=finding.id,
        event_type=event_type,
        old_value=str(previous_assignee) if previous_assignee else None,
        new_value=str(body.user_id) if body.user_id else None,
        user_id=user.id,
    )

    await db.commit()
    await db.refresh(finding)

    # Eagerly load assignee for the response
    if finding.assigned_to:
        assignee_result = await db.execute(
            select(User).where(User.id == finding.assigned_to)
        )
        assignee_user = assignee_result.scalar_one_or_none()
    else:
        assignee_user = None

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="finding.assign" if body.user_id else "finding.unassign",
        resource_type="finding",
        resource_id=str(finding.id),
        detail=f"Assigned to {body.user_id}" if body.user_id else f"Unassigned from {previous_assignee}",
    )
    await db.commit()

    data = {
        "id": finding.id,
        "status": finding.status,
        "severity": finding.severity,
        "title": finding.title,
        "dedup_key": finding.dedup_key,
        "waived": finding.waived,
        "first_detected_at": finding.first_detected_at,
        "last_evaluated_at": finding.last_evaluated_at,
        "cloud_account_id": finding.cloud_account_id,
        "asset_id": finding.asset_id,
        "control_id": finding.control_id,
        "scan_id": finding.scan_id,
        "assigned_to": finding.assigned_to,
        "assignee_email": assignee_user.email if assignee_user else None,
        "assignee_name": assignee_user.full_name if assignee_user else None,
    }

    logger.info(
        "Finding %s assigned to %s by user %s",
        finding_id,
        body.user_id,
        user.id,
    )
    return {"data": data, "error": None, "meta": None}


# ── Bulk waive ──────────────────────────────────────────────────────


@router.post("/bulk-waive", response_model=ApiResponse[BulkWaiveResult])
async def bulk_waive_findings(body: BulkWaiveRequest, db: DB, user: CurrentUser) -> dict:
    if not body.finding_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No finding IDs provided"
        )

    # Verify all findings belong to tenant
    result = await db.execute(
        select(Finding.id)
        .join(CloudAccount)
        .where(Finding.id.in_(body.finding_ids), CloudAccount.tenant_id == user.tenant_id)
    )
    valid_ids = {row[0] for row in result.all()}

    # Find existing active exceptions to skip
    existing = await db.execute(
        select(Exception_.finding_id).where(
            Exception_.finding_id.in_(valid_ids),
            Exception_.status.in_(["requested", "approved"]),
        )
    )
    already_excepted = {row[0] for row in existing.all()}

    processed = 0
    for fid in valid_ids:
        if fid in already_excepted:
            continue
        exc = Exception_(finding_id=fid, reason=body.reason, status="requested")
        db.add(exc)
        # Record timeline event for each waiver request
        await record_event(
            db,
            finding_id=fid,
            event_type="waiver_requested",
            new_value="requested",
            user_id=user.id,
            details=body.reason,
        )
        processed += 1

    await db.commit()

    skipped = len(body.finding_ids) - processed
    return {
        "data": BulkWaiveResult(processed=processed, skipped=skipped),
        "error": None,
        "meta": None,
    }


# ── Comments ─────────────────────────────────────────────────────────


@router.get(
    "/{finding_id}/comments", response_model=ApiResponse[list[CommentResponse]]
)
async def list_comments(
    finding_id: uuid.UUID, db: DB, user: CurrentUser
) -> dict:
    # Validate finding belongs to tenant
    await _get_tenant_finding(db, finding_id, user.tenant_id)

    result = await db.execute(
        select(FindingComment)
        .where(FindingComment.finding_id == finding_id)
        .options(selectinload(FindingComment.user))
        .order_by(FindingComment.created_at.asc())
    )
    comments = result.scalars().all()

    data = [
        CommentResponse(
            id=c.id,
            content=c.content,
            user_id=c.user_id,
            user_email=c.user.email if c.user else None,
            user_name=c.user.full_name if c.user else None,
            created_at=c.created_at,
        )
        for c in comments
    ]
    return {"data": data, "error": None, "meta": None}


@router.post(
    "/{finding_id}/comments",
    response_model=ApiResponse[CommentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    finding_id: uuid.UUID, body: CommentCreate, db: DB, user: CurrentUser
) -> dict:
    # Validate finding belongs to tenant
    await _get_tenant_finding(db, finding_id, user.tenant_id)

    comment = FindingComment(
        finding_id=finding_id,
        user_id=user.id,
        content=body.content,
    )
    db.add(comment)
    await db.flush()

    # Record timeline event for comment
    await record_event(
        db,
        finding_id=finding_id,
        event_type="commented",
        user_id=user.id,
        details=body.content[:200],  # Truncate for timeline summary
    )

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="finding.comment.add",
        resource_type="finding",
        resource_id=str(finding_id),
        detail=f"Comment added (id={comment.id})",
    )
    await db.commit()

    data = CommentResponse(
        id=comment.id,
        content=comment.content,
        user_id=comment.user_id,
        user_email=user.email,
        user_name=user.full_name,
        created_at=comment.created_at,
    )

    logger.info(
        "Comment %s added to finding %s by user %s",
        comment.id,
        finding_id,
        user.id,
    )
    return {"data": data, "error": None, "meta": None}


@router.delete(
    "/{finding_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    finding_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
) -> None:
    # Validate finding belongs to tenant
    await _get_tenant_finding(db, finding_id, user.tenant_id)

    result = await db.execute(
        select(FindingComment).where(
            FindingComment.id == comment_id,
            FindingComment.finding_id == finding_id,
        )
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    # Only comment author or admin can delete
    if comment.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the comment author or an admin can delete this comment",
        )

    await db.delete(comment)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="finding.comment.delete",
        resource_type="finding",
        resource_id=str(finding_id),
        detail=f"Comment deleted (id={comment_id})",
    )
    await db.commit()

    logger.info(
        "Comment %s deleted from finding %s by user %s",
        comment_id,
        finding_id,
        user.id,
    )


# ── Timeline ─────────────────────────────────────────────────────────


@router.get(
    "/{finding_id}/timeline",
    response_model=ApiResponse[list[FindingEventResponse]],
)
async def get_finding_timeline(
    finding_id: uuid.UUID, db: DB, user: CurrentUser
) -> dict:
    # Validate finding belongs to tenant
    await _get_tenant_finding(db, finding_id, user.tenant_id)

    result = await db.execute(
        select(FindingEvent)
        .where(FindingEvent.finding_id == finding_id)
        .options(selectinload(FindingEvent.user))
        .order_by(FindingEvent.created_at.desc())
    )
    events = result.scalars().all()

    data = [
        FindingEventResponse(
            id=ev.id,
            event_type=ev.event_type,
            old_value=ev.old_value,
            new_value=ev.new_value,
            user_id=ev.user_id,
            user_email=ev.user.email if ev.user else None,
            details=ev.details,
            created_at=ev.created_at,
        )
        for ev in events
    ]
    return {"data": data, "error": None, "meta": None}
