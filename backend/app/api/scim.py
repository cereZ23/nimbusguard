"""SCIM 2.0 API endpoints (RFC 7644).

These endpoints sit at ``/scim/v2/`` (outside the ``/api/v1/`` prefix) and use
their own bearer-token auth backed by API keys with the ``scim`` scope.
Responses use ``application/scim+json`` content type per the RFC.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.scim import (
    ScimListResponse,
    ScimPatchRequest,
    ScimResourceType,
    ScimSchema,
    ScimSchemaAttribute,
    ScimServiceProviderConfig,
    ScimUser,
)
from app.services.scim import (
    apply_scim_filters,
    apply_scim_patch,
    parse_scim_filter,
    scim_resource_to_user_data,
    user_to_scim_resource,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────


class ScimResponse(JSONResponse):
    """JSONResponse with ``application/scim+json`` content type."""

    media_type = "application/scim+json"


def _scim_error(status_code: int, detail: str, scim_type: str | None = None) -> ScimResponse:
    """Build a SCIM-compliant error response."""
    body: dict[str, Any] = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "status": str(status_code),
        "detail": detail,
    }
    if scim_type:
        body["scimType"] = scim_type
    return ScimResponse(status_code=status_code, content=body)


# ── SCIM Bearer Token Auth ────────────────────────────────────────────


async def get_scim_tenant(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Authenticate via SCIM bearer token and return the associated tenant_id.

    The bearer token must be an API key (``cspm_`` prefix) whose ``scopes``
    include ``"scim"``.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization",
        )

    token = auth_header.split(" ", 1)[1]
    if not token.startswith("cspm_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SCIM token format",
        )

    key_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SCIM token",
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SCIM token is inactive",
        )

    if api_key.expires_at is not None:
        expires = api_key.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="SCIM token has expired",
            )

    # Verify the key has the 'scim' scope
    scopes = api_key.scopes or []
    if "scim" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key does not have SCIM scope",
        )

    # Update last_used_at
    api_key.last_used_at = datetime.now(UTC)
    await db.commit()

    logger.info("SCIM auth: prefix=%s tenant=%s", api_key.key_prefix, api_key.tenant_id)
    return api_key.tenant_id


ScimTenant = Annotated[uuid.UUID, Depends(get_scim_tenant)]
DB = Annotated[AsyncSession, Depends(get_db)]


# ── Discovery endpoints ──────────────────────────────────────────────


@router.get("/ServiceProviderConfig")
async def service_provider_config() -> ScimResponse:
    """SCIM Service Provider Configuration (RFC 7644 Section 4)."""
    config = ScimServiceProviderConfig()
    return ScimResponse(content=config.model_dump())


@router.get("/Schemas")
async def schemas() -> ScimResponse:
    """SCIM Schema discovery (RFC 7644 Section 4)."""
    user_schema = ScimSchema(
        id="urn:ietf:params:scim:schemas:core:2.0:User",
        name="User",
        description="User Account",
        attributes=[
            ScimSchemaAttribute(
                name="userName",
                type="string",
                required=True,
                uniqueness="server",
                description="Unique identifier for the user, typically email",
            ),
            ScimSchemaAttribute(
                name="name",
                type="complex",
                description="The components of the user's name",
            ),
            ScimSchemaAttribute(
                name="displayName",
                type="string",
                description="The name displayed for the user",
            ),
            ScimSchemaAttribute(
                name="emails",
                type="complex",
                multiValued=True,
                description="Email addresses for the user",
            ),
            ScimSchemaAttribute(
                name="active",
                type="boolean",
                description="Whether the user account is active",
            ),
            ScimSchemaAttribute(
                name="externalId",
                type="string",
                description="External identifier from the identity provider",
            ),
        ],
    )
    return ScimResponse(
        content={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 1,
            "Resources": [user_schema.model_dump()],
        }
    )


@router.get("/ResourceTypes")
async def resource_types() -> ScimResponse:
    """SCIM Resource Types (RFC 7644 Section 4)."""
    rt = ScimResourceType()
    return ScimResponse(
        content={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 1,
            "Resources": [rt.model_dump(by_alias=True)],
        }
    )


# ── User CRUD ─────────────────────────────────────────────────────────


@router.get("/Users")
async def list_users(
    db: DB,
    tenant_id: ScimTenant,
    request: Request,
    filter: str | None = Query(None, alias="filter"),
    startIndex: int = Query(1, ge=1),
    count: int = Query(20, ge=1, le=200),
) -> ScimResponse:
    """List/search users (SCIM RFC 7644 Section 3.4.2)."""
    base_url = str(request.base_url).rstrip("/")

    query = select(User).where(User.tenant_id == tenant_id)

    # Apply SCIM filter
    filters = parse_scim_filter(filter)
    query = await apply_scim_filters(query, filters)

    # Count total results
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Pagination — SCIM uses 1-based startIndex
    offset = startIndex - 1
    query = query.order_by(User.created_at).offset(offset).limit(count)
    result = await db.execute(query)
    users = result.scalars().all()

    resources = [user_to_scim_resource(u, base_url) for u in users]

    response = ScimListResponse(
        totalResults=total,
        startIndex=startIndex,
        itemsPerPage=count,
        Resources=resources,
    )
    return ScimResponse(content=response.model_dump())


@router.get("/Users/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    db: DB,
    tenant_id: ScimTenant,
    request: Request,
) -> ScimResponse:
    """Get a single user (SCIM RFC 7644 Section 3.4.1)."""
    base_url = str(request.base_url).rstrip("/")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return _scim_error(404, "User not found")

    return ScimResponse(
        status_code=200,
        content=user_to_scim_resource(user, base_url),
    )


@router.post("/Users", status_code=201)
async def create_user(
    body: ScimUser,
    db: DB,
    tenant_id: ScimTenant,
    request: Request,
) -> ScimResponse:
    """Create (provision) a user (SCIM RFC 7644 Section 3.3)."""
    base_url = str(request.base_url).rstrip("/")

    scim_data = body.model_dump(exclude_none=False)
    user_data = scim_resource_to_user_data(scim_data)

    if not user_data.get("email"):
        return _scim_error(400, "userName (email) is required", scim_type="invalidValue")

    # Check for existing user with same email
    existing = await db.execute(
        select(User).where(User.email == user_data["email"])
    )
    if existing.scalar_one_or_none() is not None:
        return _scim_error(409, f"User with email {user_data['email']} already exists", scim_type="uniqueness")

    # Create user with a random password (SCIM-provisioned users use SSO to login)
    user = User(
        tenant_id=tenant_id,
        email=user_data["email"],
        full_name=user_data.get("full_name", ""),
        hashed_password=f"scim_provisioned_{secrets.token_hex(32)}",
        role="viewer",  # SCIM-provisioned users default to viewer
        is_active=user_data.get("is_active", True),
        scim_external_id=user_data.get("scim_external_id"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("SCIM: created user %s (email=%s, tenant=%s)", user.id, user.email, tenant_id)

    return ScimResponse(
        status_code=201,
        content=user_to_scim_resource(user, base_url),
        headers={"Location": f"{base_url}/scim/v2/Users/{user.id}"},
    )


@router.put("/Users/{user_id}")
async def replace_user(
    user_id: uuid.UUID,
    body: ScimUser,
    db: DB,
    tenant_id: ScimTenant,
    request: Request,
) -> ScimResponse:
    """Replace a user (SCIM RFC 7644 Section 3.5.1)."""
    base_url = str(request.base_url).rstrip("/")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return _scim_error(404, "User not found")

    scim_data = body.model_dump(exclude_none=False)
    user_data = scim_resource_to_user_data(scim_data)

    if user_data.get("email"):
        # Check uniqueness for new email
        if user_data["email"] != user.email:
            existing = await db.execute(
                select(User).where(User.email == user_data["email"])
            )
            if existing.scalar_one_or_none() is not None:
                return _scim_error(409, f"User with email {user_data['email']} already exists", scim_type="uniqueness")
        user.email = user_data["email"]

    if user_data.get("full_name"):
        user.full_name = user_data["full_name"]

    if "is_active" in user_data:
        user.is_active = user_data["is_active"]

    if "scim_external_id" in user_data:
        user.scim_external_id = user_data["scim_external_id"]

    await db.commit()
    await db.refresh(user)

    logger.info("SCIM: replaced user %s (tenant=%s)", user.id, tenant_id)

    return ScimResponse(
        status_code=200,
        content=user_to_scim_resource(user, base_url),
    )


@router.patch("/Users/{user_id}")
async def patch_user(
    user_id: uuid.UUID,
    body: ScimPatchRequest,
    db: DB,
    tenant_id: ScimTenant,
    request: Request,
) -> ScimResponse:
    """Partially update a user (SCIM RFC 7644 Section 3.5.2)."""
    base_url = str(request.base_url).rstrip("/")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return _scim_error(404, "User not found")

    operations = [op.model_dump() for op in body.Operations]
    apply_scim_patch(user, operations)

    await db.commit()
    await db.refresh(user)

    logger.info("SCIM: patched user %s (tenant=%s)", user.id, tenant_id)

    return ScimResponse(
        status_code=200,
        content=user_to_scim_resource(user, base_url),
    )


@router.delete("/Users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: DB,
    tenant_id: ScimTenant,
) -> ScimResponse:
    """Deactivate a user (soft delete per SCIM best practice).

    Sets ``is_active=False`` instead of hard-deleting.
    """
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return _scim_error(404, "User not found")

    user.is_active = False
    await db.commit()

    logger.info("SCIM: deactivated user %s (tenant=%s)", user.id, tenant_id)

    return ScimResponse(status_code=204, content=None)
