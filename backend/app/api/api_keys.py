from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse
from app.schemas.common import ApiResponse, PaginationMeta
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ApiResponse[list[ApiKeyResponse]])
async def list_api_keys(
    db: DB,
    user: AdminUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    """List all API keys for the current tenant."""
    tenant_id = user.tenant_id

    query = select(ApiKey).where(ApiKey.tenant_id == tenant_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(ApiKey.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    keys = result.scalars().all()

    return {
        "data": keys,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.post("", response_model=ApiResponse[ApiKeyCreated], status_code=status.HTTP_201_CREATED)
async def create_api_key(body: ApiKeyCreate, db: DB, user: AdminUser) -> dict:
    """Create a new API key. The full key is returned only once."""
    full_key, prefix, key_hash = ApiKey.generate_key()

    expires_at = None
    if body.expires_in_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)

    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="api_key.create",
        resource_type="api_key",
        resource_id=str(api_key.id),
        detail=f"Created API key: {api_key.name} (prefix: {prefix})",
    )
    await db.commit()

    logger.info("API key created: %s (prefix=%s) by user=%s", api_key.id, prefix, user.id)

    # Build response manually to include the full key
    response_data = {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
        "expires_at": api_key.expires_at,
        "last_used_at": api_key.last_used_at,
        "created_at": api_key.created_at,
        "api_key": full_key,
    }

    return {"data": response_data, "error": None, "meta": None}


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, db: DB, user: AdminUser) -> None:
    """Revoke (delete) an API key."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == user.tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="api_key.revoke",
        resource_type="api_key",
        resource_id=str(key_id),
        detail=f"Revoked API key: {api_key.name} (prefix: {api_key.key_prefix})",
    )
    await db.delete(api_key)
    await db.commit()
    logger.info("API key revoked: %s (prefix=%s)", key_id, api_key.key_prefix)
