from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Date, case, cast, func, or_, select

from app.deps import DB, CurrentUser
from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.custom_dashboard import CustomDashboard
from app.models.finding import Finding
from app.schemas.common import ApiResponse
from app.schemas.custom_dashboard import (
    CustomDashboardCreate,
    CustomDashboardResponse,
    CustomDashboardUpdate,
    DashboardDataResponse,
    WidgetData,
)

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_WIDGET_TYPES = {
    "secure_score",
    "findings_by_severity",
    "total_assets",
    "total_findings",
    "top_failing_controls",
    "recent_findings",
    "compliance_score",
    "findings_trend",
    "assets_by_type",
}


@router.get("", response_model=ApiResponse[list[CustomDashboardResponse]])
async def list_custom_dashboards(db: DB, user: CurrentUser) -> dict:
    """List dashboards owned by the current user plus shared dashboards in the tenant."""
    result = await db.execute(
        select(CustomDashboard)
        .where(
            CustomDashboard.tenant_id == user.tenant_id,
            or_(
                CustomDashboard.user_id == user.id,
                CustomDashboard.is_shared.is_(True),
            ),
        )
        .order_by(CustomDashboard.is_default.desc(), CustomDashboard.created_at.desc())
    )
    dashboards = result.scalars().all()
    return {"data": dashboards, "error": None, "meta": None}


@router.post(
    "",
    response_model=ApiResponse[CustomDashboardResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_dashboard(body: CustomDashboardCreate, db: DB, user: CurrentUser) -> dict:
    """Create a new custom dashboard."""
    # Validate widget types
    for widget_item in body.layout:
        if widget_item.widget not in VALID_WIDGET_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown widget type: {widget_item.widget}",
            )

    # If setting as default, unset any existing default for this user
    if body.is_default:
        await _unset_default_dashboards(db, user.tenant_id, user.id)

    dashboard = CustomDashboard(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=body.name,
        description=body.description,
        layout=[w.model_dump() for w in body.layout],
        is_default=body.is_default,
        is_shared=body.is_shared,
    )
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)
    return {"data": dashboard, "error": None, "meta": None}


@router.put("/{dashboard_id}", response_model=ApiResponse[CustomDashboardResponse])
async def update_custom_dashboard(
    dashboard_id: uuid.UUID,
    body: CustomDashboardUpdate,
    db: DB,
    user: CurrentUser,
) -> dict:
    """Update name, description, layout, or flags of a custom dashboard."""
    dashboard = await _get_owned_dashboard(db, dashboard_id, user)

    # Validate widget types if layout is being updated
    if body.layout is not None:
        for widget_item in body.layout:
            if widget_item.widget not in VALID_WIDGET_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unknown widget type: {widget_item.widget}",
                )

    if body.name is not None:
        dashboard.name = body.name
    if body.description is not None:
        dashboard.description = body.description
    if body.layout is not None:
        dashboard.layout = [w.model_dump() for w in body.layout]
    if body.is_shared is not None:
        dashboard.is_shared = body.is_shared
    if body.is_default is not None:
        if body.is_default:
            await _unset_default_dashboards(db, user.tenant_id, user.id)
        dashboard.is_default = body.is_default

    await db.commit()
    await db.refresh(dashboard)
    return {"data": dashboard, "error": None, "meta": None}


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_dashboard(dashboard_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    """Delete a custom dashboard owned by the current user."""
    dashboard = await _get_owned_dashboard(db, dashboard_id, user)
    await db.delete(dashboard)
    await db.commit()


@router.get("/{dashboard_id}/data", response_model=ApiResponse[DashboardDataResponse])
async def get_dashboard_widget_data(dashboard_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    """Batch-fetch data for all widgets in a dashboard."""
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
            or_(
                CustomDashboard.user_id == user.id,
                CustomDashboard.is_shared.is_(True),
            ),
        )
    )
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

    tenant_id = user.tenant_id
    widgets_data: list[WidgetData] = []

    # Collect which widget types are needed to avoid redundant queries
    requested_types = {item["widget"] for item in dashboard.layout}

    # Pre-fetch shared data that multiple widgets may need
    findings_agg = None
    if requested_types & {"findings_by_severity", "total_findings"}:
        findings_agg = await _fetch_findings_aggregate(db, tenant_id)

    assets_data = None
    if requested_types & {"total_assets", "assets_by_type"}:
        assets_data = await _fetch_assets_data(db, tenant_id)

    for item in dashboard.layout:
        widget_type = item["widget"]
        config = item.get("config", {})
        data = await _fetch_widget_data(db, tenant_id, widget_type, config, findings_agg, assets_data)
        widgets_data.append(WidgetData(widget=widget_type, data=data))

    response = DashboardDataResponse(dashboard_id=dashboard.id, widgets=widgets_data)
    return {"data": response, "error": None, "meta": None}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_owned_dashboard(db: DB, dashboard_id: uuid.UUID, user: CurrentUser) -> CustomDashboard:
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.user_id == user.id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    return dashboard


async def _unset_default_dashboards(db: DB, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Clear is_default flag on all dashboards for a user."""
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.tenant_id == tenant_id,
            CustomDashboard.user_id == user_id,
            CustomDashboard.is_default.is_(True),
        )
    )
    for existing in result.scalars().all():
        existing.is_default = False


async def _fetch_findings_aggregate(db: DB, tenant_id: uuid.UUID) -> tuple:
    return (
        await db.execute(
            select(
                func.count(Finding.id).label("total"),
                func.count(case((Finding.status == "fail", 1))).label("fail_total"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "high"), 1))).label("high"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "medium"), 1))).label("medium"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "low"), 1))).label("low"),
            )
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
        )
    ).one()


async def _fetch_assets_data(db: DB, tenant_id: uuid.UUID) -> tuple[int, dict[str, int]]:
    type_rows = (
        await db.execute(
            select(Asset.resource_type, func.count(Asset.id).label("cnt"))
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
            .group_by(Asset.resource_type)
            .order_by(func.count(Asset.id).desc())
        )
    ).all()
    total_assets = sum(row[1] for row in type_rows)
    assets_by_type = {row[0]: row[1] for row in type_rows[:10]}
    return total_assets, assets_by_type


async def _fetch_widget_data(
    db: DB,
    tenant_id: uuid.UUID,
    widget_type: str,
    config: dict,
    findings_agg: tuple | None,
    assets_data: tuple[int, dict[str, int]] | None,
) -> dict | list | int | float | None:
    """Fetch data for a single widget type."""
    if widget_type == "secure_score":
        return await _widget_secure_score(db, tenant_id)

    if widget_type == "findings_by_severity":
        if findings_agg is None:
            findings_agg = await _fetch_findings_aggregate(db, tenant_id)
        severity_map: dict[str, int] = {}
        if findings_agg[2]:
            severity_map["high"] = findings_agg[2]
        if findings_agg[3]:
            severity_map["medium"] = findings_agg[3]
        if findings_agg[4]:
            severity_map["low"] = findings_agg[4]
        return severity_map

    if widget_type == "total_assets":
        if assets_data is None:
            assets_data = await _fetch_assets_data(db, tenant_id)
        return {"count": assets_data[0]}

    if widget_type == "total_findings":
        if findings_agg is None:
            findings_agg = await _fetch_findings_aggregate(db, tenant_id)
        return {"count": findings_agg[0] or 0}

    if widget_type == "top_failing_controls":
        return await _widget_top_failing_controls(db, tenant_id, config)

    if widget_type == "recent_findings":
        return await _widget_recent_findings(db, tenant_id, config)

    if widget_type == "compliance_score":
        return await _widget_compliance_score(db, tenant_id)

    if widget_type == "findings_trend":
        return await _widget_findings_trend(db, tenant_id, config)

    if widget_type == "assets_by_type":
        if assets_data is None:
            assets_data = await _fetch_assets_data(db, tenant_id)
        return assets_data[1]

    return None


async def _widget_secure_score(db: DB, tenant_id: uuid.UUID) -> dict:
    score_result = await db.execute(
        select(CloudAccount.metadata_)
        .where(CloudAccount.tenant_id == tenant_id, CloudAccount.status == "active")
        .limit(1)
    )
    score_row = score_result.scalar_one_or_none()
    secure_score = None
    if score_row and isinstance(score_row, dict):
        secure_score = score_row.get("secure_score")
    return {"score": secure_score}


async def _widget_top_failing_controls(db: DB, tenant_id: uuid.UUID, config: dict) -> list[dict]:
    limit = min(config.get("limit", 10), 20)
    control_rows = (
        await db.execute(
            select(
                Control.code,
                Control.name,
                Control.severity,
                func.count(case((Finding.status == "fail", 1))).label("fail_count"),
                func.count(Finding.id).label("total_count"),
            )
            .join(Finding, Finding.control_id == Control.id)
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(CloudAccount.tenant_id == tenant_id)
            .group_by(Control.id)
            .order_by(func.count(case((Finding.status == "fail", 1))).desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "code": r[0],
            "name": r[1],
            "severity": r[2],
            "fail_count": r[3],
            "total_count": r[4],
        }
        for r in control_rows
    ]


async def _widget_recent_findings(db: DB, tenant_id: uuid.UUID, config: dict) -> list[dict]:
    limit = min(config.get("limit", 5), 20)
    rows = (
        (
            await db.execute(
                select(Finding)
                .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
                .where(CloudAccount.tenant_id == tenant_id, Finding.status == "fail")
                .order_by(Finding.first_detected_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "severity": r.severity,
            "status": r.status,
            "first_detected_at": r.first_detected_at.isoformat() if r.first_detected_at else None,
        }
        for r in rows
    ]


async def _widget_compliance_score(db: DB, tenant_id: uuid.UUID) -> dict:
    """Compute a simple compliance percentage: pass / total * 100."""
    result = (
        await db.execute(
            select(
                func.count(Finding.id).label("total"),
                func.count(case((Finding.status == "pass", 1))).label("pass_count"),
            )
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(CloudAccount.tenant_id == tenant_id)
        )
    ).one()
    total = result[0] or 0
    pass_count = result[1] or 0
    score = round((pass_count / total) * 100, 1) if total > 0 else 0
    return {"score": score, "total": total, "passing": pass_count}


async def _widget_findings_trend(db: DB, tenant_id: uuid.UUID, config: dict) -> list[dict]:
    days = min(config.get("days", 30), 365)
    since = datetime.now(UTC) - timedelta(days=days)
    date_col = cast(Finding.first_detected_at, Date)

    rows = (
        await db.execute(
            select(
                date_col.label("day"),
                func.count(case((Finding.severity == "high", 1))).label("high"),
                func.count(case((Finding.severity == "medium", 1))).label("medium"),
                func.count(case((Finding.severity == "low", 1))).label("low"),
            )
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(
                CloudAccount.tenant_id == tenant_id,
                Finding.status == "fail",
                Finding.first_detected_at >= since,
            )
            .group_by(date_col)
            .order_by(date_col)
        )
    ).all()
    return [{"date": str(r[0]), "high": r[1], "medium": r[2], "low": r[3]} for r in rows]
