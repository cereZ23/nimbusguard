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


@router.get("", response_model=ApiResponse[list[ControlResponse]])
async def list_controls(
    db: DB,
    user: CurrentUser,
    framework: str | None = Query(None),
    search: str | None = Query(None),
    page: int = 1,
    size: int = 50,
) -> dict:
    tenant_id = user.tenant_id

    # Subquery for pass/fail counts scoped to tenant
    fail_count = (
        select(func.count(Finding.id))
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(
            Finding.control_id == Control.id,
            Finding.status == "fail",
            CloudAccount.tenant_id == tenant_id,
        )
        .correlate(Control)
        .scalar_subquery()
    )
    pass_count = (
        select(func.count(Finding.id))
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(
            Finding.control_id == Control.id,
            Finding.status == "pass",
            CloudAccount.tenant_id == tenant_id,
        )
        .correlate(Control)
        .scalar_subquery()
    )
    total_count = (
        select(func.count(Finding.id))
        .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
        .where(
            Finding.control_id == Control.id,
            CloudAccount.tenant_id == tenant_id,
        )
        .correlate(Control)
        .scalar_subquery()
    )

    base = select(
        Control,
        func.coalesce(pass_count, 0).label("pass_count"),
        func.coalesce(fail_count, 0).label("fail_count"),
        func.coalesce(total_count, 0).label("total_count"),
    )

    count_base = select(func.count(Control.id))
    if search:
        like = f"%{search}%"
        search_filter = Control.name.ilike(like) | Control.code.ilike(like)
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)
    if framework:
        if framework == "cis-lite":
            # Default: return all controls (they all belong to cis-lite)
            base = base.where(Control.framework == "cis-lite")
            count_base = count_base.where(Control.framework == "cis-lite")
        else:
            # Filter controls that have this framework key in framework_mappings JSONB
            fw_filter = Control.framework_mappings.has_key(framework)  # noqa: W601
            base = base.where(fw_filter)
            count_base = count_base.where(fw_filter)

    total = (await db.execute(count_base)).scalar() or 0
    result = await db.execute(
        base.order_by(Control.code).offset((page - 1) * size).limit(size)
    )
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
    page: int = 1,
    size: int = 20,
) -> dict:
    tenant_id = user.tenant_id

    # Verify control exists
    ctrl = await db.execute(select(Control).where(Control.id == control_id))
    if ctrl.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Control not found")

    base = (
        select(Finding)
        .join(CloudAccount)
        .where(Finding.control_id == control_id, CloudAccount.tenant_id == tenant_id)
    )
    count_q = (
        select(func.count(Finding.id))
        .join(CloudAccount)
        .where(Finding.control_id == control_id, CloudAccount.tenant_id == tenant_id)
    )

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        base.order_by(Finding.last_evaluated_at.desc()).offset((page - 1) * size).limit(size)
    )
    findings = result.scalars().all()

    return {
        "data": findings,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }
