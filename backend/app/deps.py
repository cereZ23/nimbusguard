from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.logging_config import tenant_id_var, user_id_var
from app.models.user import User
from app.services.auth import decode_access_token

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    # Try httpOnly cookie first, then fall back to Authorization header (for API keys / programmatic access)
    token: str | None = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization",
        )

    # API key authentication: tokens starting with "cspm_" are API keys
    if token.startswith("cspm_"):
        from app.services.api_key_auth import authenticate_api_key

        user = await authenticate_api_key(db, token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
            )

        request.state.tenant_id = str(user.tenant_id)
        request.state.user_id = str(user.id)

        # Set context vars for structured logging
        tenant_id_var.set(str(user.tenant_id))
        user_id_var.set(str(user.id))

        return user

    # Standard JWT authentication
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Reject MFA pending tokens — they must not grant full access
    if payload.get("mfa_pending"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA verification required",
        )

    result = await db.execute(select(User).options(selectinload(User.custom_role)).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    request.state.tenant_id = str(user.tenant_id)
    request.state.user_id = str(user.id)

    # Set context vars for structured logging
    tenant_id_var.set(str(user.tenant_id))
    user_id_var.set(str(user.id))

    return user


def effective_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context not available",
        )
    return tenant_id


DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
TenantID = Annotated[str, Depends(effective_tenant_id)]


def require_role(*allowed_roles: str):
    """Dependency that checks the current user has one of the allowed roles."""

    async def _check(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return Depends(_check)


AdminUser = Annotated[User, require_role("admin")]


def require_permission(permission: str):
    """Dependency factory that checks whether the current user holds a specific permission.

    Works with both legacy roles (admin/viewer) and custom roles with granular permissions.
    """

    async def _check(user: CurrentUser) -> User:
        from app.services.permissions import has_permission as _has_perm

        if not _has_perm(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )
        return user

    return Depends(_check)
