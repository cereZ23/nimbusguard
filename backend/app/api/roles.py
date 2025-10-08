from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import DB, AdminUser, CurrentUser
from app.models.role import Role
from app.schemas.common import ApiResponse
from app.schemas.role import (
    PermissionInfo,
    PermissionListResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.services.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_CATEGORIES,
    PERMISSION_DESCRIPTIONS,
    SYSTEM_ROLES,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_system_role_response(key: str, info: dict) -> dict:
    """Build a virtual RoleResponse dict for a built-in system role."""
    return {
        "id": str(uuid.UUID(int=0)) if key == "admin" else str(uuid.UUID(int=1)),
        "name": info["name"],
        "description": info["description"],
        "permissions": info["permissions"],
        "is_system": True,
        "is_active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@router.get("/permissions", response_model=ApiResponse[PermissionListResponse])
async def list_permissions(user: CurrentUser) -> dict:
    """Return all available permissions with descriptions and categories."""
    permissions = [
        PermissionInfo(
            permission=p,
            description=PERMISSION_DESCRIPTIONS.get(p, p),
            category=next(
                (cat for cat, perms in PERMISSION_CATEGORIES.items() if p in perms),
                "Other",
            ),
        )
        for p in ALL_PERMISSIONS
    ]
    return {
        "data": {
            "permissions": permissions,
            "categories": PERMISSION_CATEGORIES,
        },
        "error": None,
        "meta": None,
    }


@router.get("", response_model=ApiResponse[list[RoleResponse]])
async def list_roles(db: DB, user: CurrentUser) -> dict:
    """List all roles for the tenant, including system roles."""
    # Start with system roles
    system_roles = [
        _build_system_role_response(key, info)
        for key, info in SYSTEM_ROLES.items()
    ]

    # Fetch custom roles for this tenant
    result = await db.execute(
        select(Role)
        .where(Role.tenant_id == user.tenant_id)
        .order_by(Role.created_at)
    )
    custom_roles = result.scalars().all()

    all_roles = system_roles + [r for r in custom_roles]
    return {"data": all_roles, "error": None, "meta": None}


@router.post("", response_model=ApiResponse[RoleResponse], status_code=status.HTTP_201_CREATED)
async def create_role(body: RoleCreate, db: DB, user: AdminUser) -> dict:
    """Create a custom role for the tenant."""
    # Validate permissions
    invalid_perms = [p for p in body.permissions if p not in ALL_PERMISSIONS]
    if invalid_perms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permissions: {', '.join(invalid_perms)}",
        )

    # Check name uniqueness within tenant
    existing = await db.execute(
        select(Role).where(
            Role.tenant_id == user.tenant_id,
            Role.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{body.name}' already exists",
        )

    role = Role(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)

    logger.info("Role created: %s by %s", role.name, user.email)
    return {"data": role, "error": None, "meta": None}


@router.put("/{role_id}", response_model=ApiResponse[RoleResponse])
async def update_role(
    role_id: uuid.UUID, body: RoleUpdate, db: DB, user: AdminUser
) -> dict:
    """Update a custom role. System roles cannot be modified."""
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.tenant_id == user.tenant_id)
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be modified",
        )

    if body.permissions is not None:
        invalid_perms = [p for p in body.permissions if p not in ALL_PERMISSIONS]
        if invalid_perms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permissions: {', '.join(invalid_perms)}",
            )
        role.permissions = body.permissions

    if body.name is not None:
        # Check uniqueness
        existing = await db.execute(
            select(Role).where(
                Role.tenant_id == user.tenant_id,
                Role.name == body.name,
                Role.id != role_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{body.name}' already exists",
            )
        role.name = body.name

    if body.description is not None:
        role.description = body.description

    await db.commit()
    await db.refresh(role)

    logger.info("Role updated: %s by %s", role.name, user.email)
    return {"data": role, "error": None, "meta": None}


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: uuid.UUID, db: DB, user: AdminUser) -> None:
    """Delete a custom role. System roles cannot be deleted."""
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.tenant_id == user.tenant_id)
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be deleted",
        )

    await db.delete(role)
    await db.commit()
    logger.info("Role deleted: %s by %s", role.name, user.email)
