from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.permissions import ALL_PERMISSIONS, PERMISSION_CATEGORIES, SYSTEM_ROLES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_viewer(client: AsyncClient, admin_headers: dict) -> dict[str, str]:
    """Create a viewer user within the admin tenant and return its auth headers."""
    res = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "viewer-roles@test.com",
            "full_name": "Viewer Roles",
            "password": "Test@pass123",
            "role": "viewer",
        },
    )
    assert res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer-roles@test.com", "password": "Test@pass123"},
    )
    assert login_res.status_code == 200
    token = login_res.cookies.get("access_token")
    assert token, "access_token cookie missing after login"
    return {"Authorization": f"Bearer {token}"}


async def _create_custom_role(
    client: AsyncClient,
    admin_headers: dict,
    *,
    name: str = "Custom Role",
    description: str | None = "A test custom role",
    permissions: list[str] | None = None,
) -> dict:
    """Create a custom role and return the response data dict."""
    if permissions is None:
        permissions = ["findings:read", "assets:read"]
    res = await client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={"name": name, "description": description, "permissions": permissions},
    )
    assert res.status_code == 201
    return res.json()["data"]


# ---------------------------------------------------------------------------
# test_list_permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_permissions(client: AsyncClient, auth_headers: dict) -> None:
    """GET /roles/permissions returns all permissions with descriptions and categories."""
    res = await client.get("/api/v1/roles/permissions", headers=auth_headers)

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None

    data = body["data"]
    assert "permissions" in data
    assert "categories" in data

    returned_perms = {p["permission"] for p in data["permissions"]}
    assert returned_perms == set(ALL_PERMISSIONS)

    # Every permission must have a non-empty description and a category
    for perm_info in data["permissions"]:
        assert perm_info["description"], f"Missing description for {perm_info['permission']}"
        assert perm_info["category"], f"Missing category for {perm_info['permission']}"

    # Categories dict must match the service-level constant
    assert data["categories"] == PERMISSION_CATEGORIES


@pytest.mark.asyncio
async def test_list_permissions_requires_auth(client: AsyncClient) -> None:
    """GET /roles/permissions without token returns 401."""
    res = await client.get("/api/v1/roles/permissions")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# test_list_roles_includes_system
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_roles_includes_system(client: AsyncClient, auth_headers: dict) -> None:
    """GET /roles always includes built-in system roles (admin + viewer)."""
    res = await client.get("/api/v1/roles", headers=auth_headers)

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None

    roles = body["data"]
    role_names = {r["name"] for r in roles}

    expected_system_names = {info["name"] for info in SYSTEM_ROLES.values()}
    assert expected_system_names.issubset(role_names), (
        f"Expected system roles {expected_system_names} not found in {role_names}"
    )

    # System roles must be flagged as is_system=True
    for role in roles:
        if role["name"] in expected_system_names:
            assert role["is_system"] is True, f"Role {role['name']} should be is_system=True"


@pytest.mark.asyncio
async def test_list_roles_requires_auth(client: AsyncClient) -> None:
    """GET /roles without token returns 401."""
    res = await client.get("/api/v1/roles")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# test_create_custom_role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_custom_role(client: AsyncClient, auth_headers: dict) -> None:
    """POST /roles creates a custom role with valid permissions."""
    res = await client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={
            "name": "Security Analyst",
            "description": "Read-only access to findings and assets",
            "permissions": ["findings:read", "assets:read"],
        },
    )

    assert res.status_code == 201
    body = res.json()
    assert body["error"] is None

    data = body["data"]
    assert data["name"] == "Security Analyst"
    assert data["description"] == "Read-only access to findings and assets"
    assert set(data["permissions"]) == {"findings:read", "assets:read"}
    assert data["is_system"] is False
    assert data["is_active"] is True
    assert "id" in data

    # Verify the new role appears in the list
    list_res = await client.get("/api/v1/roles", headers=auth_headers)
    role_names = {r["name"] for r in list_res.json()["data"]}
    assert "Security Analyst" in role_names


# ---------------------------------------------------------------------------
# test_create_role_invalid_permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_role_invalid_permissions(client: AsyncClient, auth_headers: dict) -> None:
    """POST /roles with a non-existent permission returns 400."""
    res = await client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={
            "name": "Bad Role",
            "permissions": ["findings:read", "invalid:permission"],
        },
    )

    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "invalid:permission" in detail.lower() or "invalid" in detail.lower()


@pytest.mark.asyncio
async def test_create_role_empty_permissions_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """POST /roles with empty permissions list fails Pydantic validation (422)."""
    res = await client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={"name": "Empty Perms", "permissions": []},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# test_create_role_duplicate_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_role_duplicate_name(client: AsyncClient, auth_headers: dict) -> None:
    """POST /roles with a name that already exists for the tenant returns 409."""
    await _create_custom_role(client, auth_headers, name="Unique Role Name")

    res = await client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={"name": "Unique Role Name", "permissions": ["findings:read"]},
    )

    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# test_update_role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_role(client: AsyncClient, auth_headers: dict) -> None:
    """PUT /roles/{id} updates name, description, and permissions."""
    role = await _create_custom_role(
        client,
        auth_headers,
        name="Before Update",
        permissions=["findings:read"],
    )
    role_id = role["id"]

    res = await client.put(
        f"/api/v1/roles/{role_id}",
        headers=auth_headers,
        json={
            "name": "After Update",
            "description": "Updated description",
            "permissions": ["findings:read", "assets:read", "reports:read"],
        },
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["name"] == "After Update"
    assert data["description"] == "Updated description"
    assert set(data["permissions"]) == {"findings:read", "assets:read", "reports:read"}


@pytest.mark.asyncio
async def test_update_role_invalid_permissions(client: AsyncClient, auth_headers: dict) -> None:
    """PUT /roles/{id} with invalid permissions returns 400."""
    role = await _create_custom_role(client, auth_headers, name="To Patch Bad Perms")

    res = await client.put(
        f"/api/v1/roles/{role['id']}",
        headers=auth_headers,
        json={"permissions": ["findings:read", "not:a:real:permission"]},
    )

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_update_role_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """PUT /roles/{id} for a non-existent ID returns 404."""
    import uuid

    res = await client.put(
        f"/api/v1/roles/{uuid.uuid4()}",
        headers=auth_headers,
        json={"name": "Ghost"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# test_update_system_role_blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_system_role_blocked(client: AsyncClient, auth_headers: dict) -> None:
    """PUT on a system role returns 400 — system roles are immutable.

    The API only exposes *custom* roles (those persisted in the DB).
    System roles are virtual and have no real UUID, so PUT with their
    virtual UUIDs returns 404, which equally enforces immutability.
    We also persist a custom role flagged as is_system=True directly in the
    DB to cover the explicit 400 guard in the endpoint.
    """
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.role import Role

    # Obtain the tenant_id by fetching current user
    me_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_res.status_code == 200
    tenant_id = me_res.json()["data"]["tenant_id"]

    # Insert a system role directly in the DB
    engine = create_async_engine(
        "postgresql+asyncpg://cspm:cspm@localhost:5432/cspm_test",
        echo=False,
        poolclass=NullPool,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        sys_role = Role(
            tenant_id=uuid.UUID(tenant_id),
            name="__system_immutable__",
            permissions=["*"],
            is_system=True,
            is_active=True,
        )
        session.add(sys_role)
        await session.commit()
        await session.refresh(sys_role)
        sys_role_id = str(sys_role.id)
    await engine.dispose()

    res = await client.put(
        f"/api/v1/roles/{sys_role_id}",
        headers=auth_headers,
        json={"name": "Hacked System Role"},
    )
    assert res.status_code == 400
    assert "system" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# test_delete_role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_role(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /roles/{id} removes a custom role and returns 204."""
    role = await _create_custom_role(client, auth_headers, name="Delete Me")
    role_id = role["id"]

    res = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert res.status_code == 204

    # Confirm it is gone from the list
    list_res = await client.get("/api/v1/roles", headers=auth_headers)
    remaining_ids = {r["id"] for r in list_res.json()["data"]}
    assert role_id not in remaining_ids


@pytest.mark.asyncio
async def test_delete_role_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /roles/{id} for a non-existent role returns 404."""
    import uuid

    res = await client.delete(f"/api/v1/roles/{uuid.uuid4()}", headers=auth_headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# test_delete_system_role_blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_system_role_blocked(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE on a DB-persisted system role returns 400."""
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.role import Role

    me_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    tenant_id = me_res.json()["data"]["tenant_id"]

    engine = create_async_engine(
        "postgresql+asyncpg://cspm:cspm@localhost:5432/cspm_test",
        echo=False,
        poolclass=NullPool,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        sys_role = Role(
            tenant_id=uuid.UUID(tenant_id),
            name="__system_immutable_delete__",
            permissions=["*"],
            is_system=True,
            is_active=True,
        )
        session.add(sys_role)
        await session.commit()
        await session.refresh(sys_role)
        sys_role_id = str(sys_role.id)
    await engine.dispose()

    res = await client.delete(f"/api/v1/roles/{sys_role_id}", headers=auth_headers)
    assert res.status_code == 400
    assert "system" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# test_create_role_requires_admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_role_requires_admin(client: AsyncClient, auth_headers: dict) -> None:
    """A viewer user cannot create roles (must get 403)."""
    viewer_headers = await _create_viewer(client, auth_headers)

    res = await client.post(
        "/api/v1/roles",
        headers=viewer_headers,
        json={"name": "Viewer Cannot Create", "permissions": ["findings:read"]},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_update_role_requires_admin(client: AsyncClient, auth_headers: dict) -> None:
    """A viewer user cannot update roles (must get 403)."""
    role = await _create_custom_role(client, auth_headers, name="Viewer Cannot Update")
    viewer_headers = await _create_viewer(client, auth_headers)

    res = await client.put(
        f"/api/v1/roles/{role['id']}",
        headers=viewer_headers,
        json={"name": "Hijacked"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_delete_role_requires_admin(client: AsyncClient, auth_headers: dict) -> None:
    """A viewer user cannot delete roles (must get 403)."""
    role = await _create_custom_role(client, auth_headers, name="Viewer Cannot Delete")
    viewer_headers = await _create_viewer(client, auth_headers)

    res = await client.delete(
        f"/api/v1/roles/{role['id']}",
        headers=viewer_headers,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# test_roles_tenant_isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roles_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
) -> None:
    """Custom roles created by tenant A must not appear in tenant B's listing."""
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()
    await _create_custom_role(client, auth_headers, name="Tenant A Exclusive Role")

    # Clear cookies again before tenant B request
    client.cookies.clear()
    res_b = await client.get("/api/v1/roles", headers=second_auth_headers)
    assert res_b.status_code == 200

    role_names_b = {r["name"] for r in res_b.json()["data"]}
    assert "Tenant A Exclusive Role" not in role_names_b


@pytest.mark.asyncio
async def test_roles_tenant_b_cannot_delete_tenant_a_role(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
) -> None:
    """Tenant B cannot delete a role belonging to tenant A (must get 404)."""
    # Clear cookies to prevent cookie-based auth bleed
    client.cookies.clear()
    role = await _create_custom_role(client, auth_headers, name="Tenant A Private Role")

    # Clear cookies again before tenant B request
    client.cookies.clear()
    res = await client.delete(
        f"/api/v1/roles/{role['id']}",
        headers=second_auth_headers,
    )
    # Role belongs to a different tenant — treated as not found
    assert res.status_code == 404
