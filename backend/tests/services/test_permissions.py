"""Unit tests for app.services.permissions — RBAC resolution.

Covers legacy system roles (admin wildcard, viewer granular), custom roles
(wildcard + granular lists), and the unknown/malformed-role fallbacks.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth import hash_password
from app.services.permissions import (
    ALL_PERMISSIONS,
    SYSTEM_ROLES,
    get_user_permissions,
    has_permission,
)


async def _make_user(db, *, role: str = "viewer", custom_role: Role | None = None) -> User:
    tenant = Tenant(name="Perm Tenant", slug=f"perm-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    user = User(
        tenant_id=tenant.id,
        email=f"perm-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("x"),
        full_name="Perm User",
        role=role,
    )
    if custom_role is not None:
        custom_role.tenant_id = tenant.id
        db.add(custom_role)
        await db.flush()
        user.role_id = custom_role.id
        user.custom_role = custom_role
    db.add(user)
    await db.flush()
    return user


# ── Legacy roles ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_legacy_role_has_wildcard(db):
    user = await _make_user(db, role="admin")
    perms = get_user_permissions(user)
    assert perms == ["*"]
    assert has_permission(user, "users:write") is True
    assert has_permission(user, "anything:at:all") is True


@pytest.mark.asyncio
async def test_viewer_legacy_role_granular(db):
    user = await _make_user(db, role="viewer")
    perms = get_user_permissions(user)
    assert perms == SYSTEM_ROLES["viewer"]["permissions"]
    assert has_permission(user, "findings:read") is True
    # viewer must not have any write permission
    assert has_permission(user, "findings:write") is False
    assert has_permission(user, "users:write") is False


@pytest.mark.asyncio
async def test_unknown_legacy_role_returns_empty(db):
    user = await _make_user(db, role="superhacker")
    assert get_user_permissions(user) == []
    assert has_permission(user, "findings:read") is False


# ── Custom roles ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_custom_role_granular_takes_precedence(db):
    role = Role(
        name="Auditor",
        description="custom",
        permissions=["findings:read", "reports:read"],
    )
    # legacy role would grant '*', but custom role must win
    user = await _make_user(db, role="admin", custom_role=role)
    perms = get_user_permissions(user)
    assert perms == ["findings:read", "reports:read"]
    assert has_permission(user, "findings:read") is True
    assert has_permission(user, "users:write") is False  # admin wildcard ignored


@pytest.mark.asyncio
async def test_custom_role_wildcard(db):
    role = Role(name="SuperRole", permissions=["*"])
    user = await _make_user(db, role="viewer", custom_role=role)
    assert get_user_permissions(user) == ["*"]
    assert has_permission(user, "settings:write") is True


@pytest.mark.asyncio
async def test_custom_role_non_list_permissions_returns_empty(db):
    # permissions stored as a non-list (defensive branch)
    role = Role(name="Broken", permissions={"oops": True})
    user = await _make_user(db, role="viewer", custom_role=role)
    assert get_user_permissions(user) == []
    assert has_permission(user, "findings:read") is False


@pytest.mark.asyncio
async def test_custom_role_covers_every_known_permission(db):
    role = Role(name="Everything", permissions=list(ALL_PERMISSIONS))
    user = await _make_user(db, role="viewer", custom_role=role)
    for perm in ALL_PERMISSIONS:
        assert has_permission(user, perm) is True
