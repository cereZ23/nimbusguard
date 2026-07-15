from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select

from app.deps import DB, CurrentUser
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.finding import Finding
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.controls import ControlResponse
from app.schemas.findings import FindingResponse

router = APIRouter()

# Frameworks stored directly in Control.framework (one control belongs to
# exactly one). Everything else filters framework_mappings JSONB keys.
PRIMARY_FRAMEWORKS = {"cis-lite", "cis-m365"}


@router.get("", response_model=ApiResponse[list[ControlResponse]])
async def list_controls(
    db: DB,
    user: CurrentUser,
    framework: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> dict:
    tenant_id = user.tenant_id

    # Single grouped LEFT JOIN instead of 3 correlated subqueries
    # This reduces 3*N subquery evaluations to 1 join + group
    counts_subq = (
        select(
            Finding.control_id,
            func.count(case((Finding.status == "pass", 1))).label("pass_count"),
            func.count(case((Finding.status == "fail", 1))).label("fail_count"),
            func.count(Finding.id).label("total_count"),
        )
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(CloudAccount.tenant_id == tenant_id)
        .group_by(Finding.control_id)
        .subquery()
    )

    base = select(
        Control,
        func.coalesce(counts_subq.c.pass_count, 0).label("pass_count"),
        func.coalesce(counts_subq.c.fail_count, 0).label("fail_count"),
        func.coalesce(counts_subq.c.total_count, 0).label("total_count"),
    ).outerjoin(counts_subq, Control.id == counts_subq.c.control_id)

    count_base = select(func.count(Control.id))
    if search:
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        like = f"%{escaped}%"
        search_filter = Control.name.ilike(like, escape="\\") | Control.code.ilike(like, escape="\\")
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)
    if framework:
        if framework in PRIMARY_FRAMEWORKS:
            # Primary frameworks filter directly on Control.framework
            base = base.where(Control.framework == framework)
            count_base = count_base.where(Control.framework == framework)
        else:
            # Filter controls that have this framework key in framework_mappings JSONB
            fw_filter = Control.framework_mappings.has_key(framework)  # noqa: W601
            base = base.where(fw_filter)
            count_base = count_base.where(fw_filter)

    total = (await db.execute(count_base)).scalar() or 0
    result = await db.execute(base.order_by(Control.code).offset((page - 1) * size).limit(size))
    rows = result.all()

    controls = []
    for row in rows:
        ctrl = row[0]
        controls.append(
            ControlResponse(
                id=ctrl.id,
                code=ctrl.code,
                name=ctrl.name,
                description=ctrl.description,
                severity=ctrl.severity,
                framework=ctrl.framework,
                remediation_hint=ctrl.remediation_hint,
                framework_mappings=ctrl.framework_mappings,
                automation=ctrl.automation,
                pass_count=row[1],
                fail_count=row[2],
                total_count=row[3],
            )
        )

    return {
        "data": controls,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.get("/{control_id}", response_model=ApiResponse[ControlResponse])
async def get_control(control_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    tenant_id = user.tenant_id

    result = await db.execute(select(Control).where(Control.id == control_id))
    ctrl = result.scalar_one_or_none()
    if ctrl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    # Count findings for this control scoped to tenant
    counts = (
        await db.execute(
            select(
                func.count(case((Finding.status == "pass", 1))).label("pass_count"),
                func.count(case((Finding.status == "fail", 1))).label("fail_count"),
                func.count(Finding.id).label("total_count"),
            )
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(Finding.control_id == control_id, CloudAccount.tenant_id == tenant_id)
        )
    ).one()

    return {
        "data": ControlResponse(
            id=ctrl.id,
            code=ctrl.code,
            name=ctrl.name,
            description=ctrl.description,
            severity=ctrl.severity,
            framework=ctrl.framework,
            remediation_hint=ctrl.remediation_hint,
            framework_mappings=ctrl.framework_mappings,
            pass_count=counts[0],
            fail_count=counts[1],
            total_count=counts[2],
        ),
        "error": None,
        "meta": None,
    }


@router.get("/{control_id}/findings", response_model=ApiResponse[list[FindingResponse]])
async def list_control_findings(
    control_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    tenant_id = user.tenant_id

    # Verify control exists
    ctrl = await db.execute(select(Control).where(Control.id == control_id))
    if ctrl.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    base = (
        select(Finding).join(CloudAccount).where(Finding.control_id == control_id, CloudAccount.tenant_id == tenant_id)
    )
    count_q = (
        select(func.count(Finding.id))
        .join(CloudAccount)
        .where(Finding.control_id == control_id, CloudAccount.tenant_id == tenant_id)
    )

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(base.order_by(Finding.last_evaluated_at.desc()).offset((page - 1) * size).limit(size))
    findings = result.scalars().all()

    return {
        "data": findings,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }
