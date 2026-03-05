from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models.saved_filter import SavedFilter
from app.schemas.common import ApiResponse
from app.schemas.saved_filter import SavedFilterCreate, SavedFilterResponse

router = APIRouter()


@router.get("", response_model=ApiResponse[list[SavedFilterResponse]])
async def list_saved_filters(
    db: DB,
    user: CurrentUser,
    page_filter: str | None = Query(None, alias="page"),
) -> dict:
    base = select(SavedFilter).where(
        SavedFilter.tenant_id == user.tenant_id,
        SavedFilter.user_id == user.id,
    )
    if page_filter:
        base = base.where(SavedFilter.page == page_filter)

    result = await db.execute(base.order_by(SavedFilter.created_at.desc()))
    filters = result.scalars().all()

    return {"data": filters, "error": None, "meta": None}


@router.post(
    "",
    response_model=ApiResponse[SavedFilterResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_filter(body: SavedFilterCreate, db: DB, user: CurrentUser) -> dict:
    sf = SavedFilter(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=body.name,
        page=body.page,
        filters=body.filters,
        description=body.description,
    )
    db.add(sf)
    await db.commit()
    await db.refresh(sf)
    return {"data": sf, "error": None, "meta": None}


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_filter(filter_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    result = await db.execute(
        select(SavedFilter).where(
            SavedFilter.id == filter_id,
            SavedFilter.user_id == user.id,
            SavedFilter.tenant_id == user.tenant_id,
        )
    )
    sf = result.scalar_one_or_none()
    if sf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved filter not found")
    await db.delete(sf)
    await db.commit()
