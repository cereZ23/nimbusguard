from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from sqlalchemy.orm import selectinload

from app.deps import DB, AdminUser, CurrentUser
from app.models.role import Role
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.users import InviteUserRequest, UpdateRoleRequest, UserResponse
from app.services.auth import hash_password

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(db: DB, user: CurrentUser) -> dict:
    result = await db.execute(
        select(User)
        .options(selectinload(User.custom_role))
        .where(User.tenant_id == user.tenant_id)
        .order_by(User.created_at)
    )
    users = result.scalars().all()
    data = []
    for u in users:
        user_dict = {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "role_id": u.role_id,
            "role_name": u.custom_role.name if u.custom_role else None,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        data.append(user_dict)
    return {"data": data, "error": None, "meta": None}


@router.post("", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def invite_user(body: InviteUserRequest, db: DB, user: AdminUser) -> dict:
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # If role_id is provided, validate it belongs to the tenant
    if body.role_id is not None:
        role_result = await db.execute(
            select(Role).where(Role.id == body.role_id, Role.tenant_id == user.tenant_id)
        )
        custom_role = role_result.scalar_one_or_none()
        if custom_role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role_id — role not found in this tenant",
            )

    new_user = User(
        tenant_id=user.tenant_id,
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        role_id=body.role_id,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info("User invited: %s (role=%s, role_id=%s) by %s", body.email, body.role, body.role_id, user.email)
    return {"data": new_user, "error": None, "meta": None}


@router.put("/{user_id}/role", response_model=ApiResponse[UserResponse])
async def update_user_role(
    user_id: uuid.UUID, body: UpdateRoleRequest, db: DB, user: AdminUser
) -> dict:
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    # Handle role_id assignment (custom role)
    if body.role_id is not None:
        role_result = await db.execute(
            select(Role).where(Role.id == body.role_id, Role.tenant_id == user.tenant_id)
        )
        custom_role = role_result.scalar_one_or_none()
        if custom_role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role_id — role not found in this tenant",
            )
        target.role_id = body.role_id
        # Keep legacy role field in sync: custom roles are neither admin nor viewer
        if body.role is None:
            target.role = "viewer"
    else:
        # Clear custom role when switching to a system role
        target.role_id = None

    if body.role is not None:
        target.role = body.role

    await db.commit()
    await db.refresh(target)

    logger.info(
        "User %s role updated to %s (role_id=%s) by %s",
        target.email, target.role, target.role_id, user.email,
    )
    return {"data": target, "error": None, "meta": None}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(user_id: uuid.UUID, db: DB, user: AdminUser) -> None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself",
        )

    await db.delete(target)
    await db.commit()
    logger.info("User %s removed by %s", target.email, user.email)
