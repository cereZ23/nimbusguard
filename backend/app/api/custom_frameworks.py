from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser, CurrentUser
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.custom_framework import CustomFramework
from app.models.finding import Finding
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.custom_framework import (
    ControlComplianceItem,
    CustomFrameworkCompliance,
    CustomFrameworkCreate,
    CustomFrameworkResponse,
    CustomFrameworkUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=ApiResponse[list[CustomFrameworkResponse]])
async def list_custom_frameworks(
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> dict:
    """List custom frameworks for the current tenant."""
    tenant_id = user.tenant_id

    count_q = select(func.count(CustomFramework.id)).where(CustomFramework.tenant_id == tenant_id)
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        select(CustomFramework)
        .where(CustomFramework.tenant_id == tenant_id)
        .order_by(CustomFramework.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    frameworks = result.scalars().all()

    return {
        "data": frameworks,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.post(
    "",
    response_model=ApiResponse[CustomFrameworkResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_framework(
    body: CustomFrameworkCreate,
    db: DB,
    user: AdminUser,
) -> dict:
    """Create a new custom compliance framework (admin only)."""
    # Validate that all referenced control codes exist
    control_codes = [m.control_code for m in body.control_mappings]
    result = await db.execute(select(Control.code).where(Control.code.in_(control_codes)))
    existing_codes = {row[0] for row in result.all()}
    invalid_codes = set(control_codes) - existing_codes
    if invalid_codes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown control codes: {', '.join(sorted(invalid_codes))}",
        )

    framework = CustomFramework(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        control_mappings=[m.model_dump() for m in body.control_mappings],
        created_by=user.id,
    )
    db.add(framework)
    await db.commit()
    await db.refresh(framework)

    logger.info(
        "Custom framework created",
        extra={"framework_id": str(framework.id), "tenant_id": str(user.tenant_id)},
    )

    return {"data": framework, "error": None, "meta": None}


@router.get("/{framework_id}", response_model=ApiResponse[CustomFrameworkResponse])
async def get_custom_framework(
    framework_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
) -> dict:
    """Get a single custom framework by ID."""
    framework = await _get_framework_or_404(db, framework_id, user.tenant_id)
    return {"data": framework, "error": None, "meta": None}


@router.put("/{framework_id}", response_model=ApiResponse[CustomFrameworkResponse])
async def update_custom_framework(
    framework_id: uuid.UUID,
    body: CustomFrameworkUpdate,
    db: DB,
    user: AdminUser,
) -> dict:
    """Update an existing custom framework (admin only)."""
    framework = await _get_framework_or_404(db, framework_id, user.tenant_id)

    if body.name is not None:
        framework.name = body.name
    if body.description is not None:
        framework.description = body.description
    if body.is_active is not None:
        framework.is_active = body.is_active
    if body.control_mappings is not None:
        # Validate control codes
        control_codes = [m.control_code for m in body.control_mappings]
        result = await db.execute(select(Control.code).where(Control.code.in_(control_codes)))
        existing_codes = {row[0] for row in result.all()}
        invalid_codes = set(control_codes) - existing_codes
        if invalid_codes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown control codes: {', '.join(sorted(invalid_codes))}",
            )
        framework.control_mappings = [m.model_dump() for m in body.control_mappings]

    await db.commit()
    await db.refresh(framework)

    logger.info(
        "Custom framework updated",
        extra={"framework_id": str(framework.id), "tenant_id": str(user.tenant_id)},
    )

    return {"data": framework, "error": None, "meta": None}


@router.delete("/{framework_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_framework(
    framework_id: uuid.UUID,
    db: DB,
    user: AdminUser,
) -> None:
    """Delete a custom framework (admin only)."""
    framework = await _get_framework_or_404(db, framework_id, user.tenant_id)
    await db.delete(framework)
    await db.commit()

    logger.info(
        "Custom framework deleted",
        extra={"framework_id": str(framework_id), "tenant_id": str(user.tenant_id)},
    )


@router.get(
    "/{framework_id}/compliance",
    response_model=ApiResponse[CustomFrameworkCompliance],
)
async def get_custom_framework_compliance(
    framework_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
) -> dict:
    """Get compliance data for a custom framework (pass/fail per control)."""
    tenant_id = user.tenant_id
    framework = await _get_framework_or_404(db, framework_id, tenant_id)

    # Extract control codes from framework mappings
    mappings = framework.control_mappings or []
    control_codes = [m["control_code"] for m in mappings]
    if not control_codes:
        return {
            "data": CustomFrameworkCompliance(
                framework_id=framework.id,
                framework_name=framework.name,
                controls=[],
                total_controls=0,
                passing_controls=0,
                failing_controls=0,
            ),
            "error": None,
            "meta": None,
        }

    # Build a lookup from control_code to group/reference from the framework mapping
    mapping_lookup: dict[str, dict[str, str]] = {}
    for m in mappings:
        mapping_lookup[m["control_code"]] = {
            "group": m.get("group", ""),
            "reference": m.get("reference", ""),
        }

    # Subqueries for pass/fail/total counts scoped to tenant
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

    result = await db.execute(
        select(
            Control,
            func.coalesce(pass_count, 0).label("pass_count"),
            func.coalesce(fail_count, 0).label("fail_count"),
            func.coalesce(total_count, 0).label("total_count"),
        )
        .where(Control.code.in_(control_codes))
        .order_by(Control.code)
    )
    rows = result.all()

    controls: list[ControlComplianceItem] = []
    passing_controls = 0
    failing_controls = 0

    for row in rows:
        ctrl = row[0]
        p_count = row[1]
        f_count = row[2]
        t_count = row[3]

        extra = mapping_lookup.get(ctrl.code, {"group": "", "reference": ""})

        controls.append(
            ControlComplianceItem(
                control_code=ctrl.code,
                control_name=ctrl.name,
                severity=ctrl.severity,
                group=extra["group"],
                reference=extra["reference"],
                pass_count=p_count,
                fail_count=f_count,
                total_count=t_count,
            )
        )

        if t_count > 0 and f_count == 0:
            passing_controls += 1
        elif f_count > 0:
            failing_controls += 1

    compliance = CustomFrameworkCompliance(
        framework_id=framework.id,
        framework_name=framework.name,
        controls=controls,
        total_controls=len(controls),
        passing_controls=passing_controls,
        failing_controls=failing_controls,
    )

    return {"data": compliance, "error": None, "meta": None}


async def _get_framework_or_404(
    db: DB,
    framework_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> CustomFramework:
    """Fetch a custom framework scoped to tenant, or raise 404."""
    result = await db.execute(
        select(CustomFramework).where(
            CustomFramework.id == framework_id,
            CustomFramework.tenant_id == tenant_id,
        )
    )
    framework = result.scalar_one_or_none()
    if framework is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom framework not found",
        )
    return framework
