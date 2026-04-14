from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, CurrentUser
from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.schemas.assets import AssetResponse
from app.schemas.common import ApiResponse, PaginationMeta

router = APIRouter()


@router.get("", response_model=ApiResponse[list[AssetResponse]])
async def list_assets(
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    resource_type: str | None = Query(None),
    region: str | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("name", pattern=r"^(name|resource_type|region|first_seen_at|last_seen_at)$"),
    sort_order: str = Query("asc", pattern=r"^(asc|desc)$"),
) -> dict:
    base = select(Asset).join(CloudAccount).where(CloudAccount.tenant_id == user.tenant_id)
    count_base = select(func.count(Asset.id)).join(CloudAccount).where(CloudAccount.tenant_id == user.tenant_id)

    if search:
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        like = f"%{escaped}%"
        base = base.where(Asset.name.ilike(like, escape="\\"))
        count_base = count_base.where(Asset.name.ilike(like, escape="\\"))
    if resource_type:
        base = base.where(Asset.resource_type == resource_type)
        count_base = count_base.where(Asset.resource_type == resource_type)
    if region:
        base = base.where(Asset.region == region)
        count_base = count_base.where(Asset.region == region)
    if account_id:
        base = base.where(Asset.cloud_account_id == account_id)
        count_base = count_base.where(Asset.cloud_account_id == account_id)

    total = (await db.execute(count_base)).scalar() or 0

    sort_col = getattr(Asset, sort_by)
    order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
    result = await db.execute(base.order_by(order).offset((page - 1) * size).limit(size))
    assets = result.scalars().all()

    return {
        "data": assets,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.get("/{asset_id}", response_model=ApiResponse[AssetResponse])
async def get_asset(asset_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    result = await db.execute(
        select(Asset).join(CloudAccount).where(Asset.id == asset_id, CloudAccount.tenant_id == user.tenant_id)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return {"data": asset, "error": None, "meta": None}
