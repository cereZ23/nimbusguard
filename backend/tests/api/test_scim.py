"""Tests for SCIM 2.0 provisioning endpoints (/scim/v2/)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User

# ── Helpers ───────────────────────────────────────────────────────────


async def _create_scim_token(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Create an API key with SCIM scope and return the full key string."""
    full_key, prefix, key_hash = ApiKey.generate_key()
    api_key = ApiKey(
        tenant_id=tenant_id,
        user_id=user_id,
        name="SCIM Provisioning",
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=["scim"],
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    return full_key


async def _get_tenant_and_user(db: AsyncSession, email: str = "usera@test.com") -> tuple[uuid.UUID, uuid.UUID]:
    """Look up a user by email and return (tenant_id, user_id)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    return user.tenant_id, user.id


@pytest.fixture
async def scim_headers(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> dict[str, str]:
    """Register a user, create a SCIM API key, return auth headers for SCIM."""
    # auth_headers fixture already registered usera@test.com
    tenant_id, user_id = await _get_tenant_and_user(db)
    token = await _create_scim_token(db, tenant_id, user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def scim_tenant_id(db: AsyncSession) -> uuid.UUID:
    """Return the tenant_id for the registered test user."""
    tenant_id, _ = await _get_tenant_and_user(db)
    return tenant_id


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_service_provider_config(client: AsyncClient) -> None:
    """GET /scim/v2/ServiceProviderConfig returns valid SCIM config (no auth needed for discovery)."""
    res = await client.get("/scim/v2/ServiceProviderConfig")
    assert res.status_code == 200
    data = res.json()
    assert "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig" in data["schemas"]
    assert data["patch"]["supported"] is True
    assert data["filter"]["supported"] is True
    assert data["bulk"]["supported"] is False


@pytest.mark.asyncio
async def test_schemas_endpoint(client: AsyncClient) -> None:
    """GET /scim/v2/Schemas returns the User schema."""
    res = await client.get("/scim/v2/Schemas")
    assert res.status_code == 200
    data = res.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["id"] == "urn:ietf:params:scim:schemas:core:2.0:User"


@pytest.mark.asyncio
async def test_resource_types_endpoint(client: AsyncClient) -> None:
    """GET /scim/v2/ResourceTypes returns User resource type."""
    res = await client.get("/scim/v2/ResourceTypes")
    assert res.status_code == 200
    data = res.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["name"] == "User"


@pytest.mark.asyncio
async def test_unauthorized_no_token(client: AsyncClient, auth_headers: dict) -> None:
    """SCIM user endpoints require a SCIM bearer token; JWT tokens should fail."""
    res = await client.get("/scim/v2/Users")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_jwt_token(client: AsyncClient, auth_headers: dict) -> None:
    """A valid JWT token should not work for SCIM endpoints (wrong format)."""
    res = await client.get("/scim/v2/Users", headers=auth_headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_wrong_scope(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """An API key without 'scim' scope should be rejected with 403."""
    tenant_id, user_id = await _get_tenant_and_user(db)
    full_key, prefix, key_hash = ApiKey.generate_key()
    api_key = ApiKey(
        tenant_id=tenant_id,
        user_id=user_id,
        name="Read Only Key",
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=["read"],
        is_active=True,
    )
    db.add(api_key)
    await db.commit()

    res = await client.get(
        "/scim/v2/Users",
        headers={"Authorization": f"Bearer {full_key}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, scim_headers: dict) -> None:
    """POST /scim/v2/Users creates a new user."""
    res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "scim-user@example.com",
            "name": {
                "givenName": "SCIM",
                "familyName": "User",
            },
            "emails": [{"value": "scim-user@example.com", "primary": True}],
            "active": True,
            "externalId": "ext-001",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["userName"] == "scim-user@example.com"
    assert data["active"] is True
    assert data["externalId"] == "ext-001"
    assert data["name"]["givenName"] == "SCIM"
    assert data["name"]["familyName"] == "User"
    assert data["id"] is not None
    # Check Location header
    assert "Location" in res.headers
    assert data["id"] in res.headers["Location"]


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient, scim_headers: dict) -> None:
    """POST /scim/v2/Users with an existing email returns 409."""
    user_data = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": "duplicate@example.com",
        "name": {"givenName": "Dup", "familyName": "User"},
        "active": True,
    }
    res1 = await client.post("/scim/v2/Users", headers=scim_headers, json=user_data)
    assert res1.status_code == 201

    res2 = await client.post("/scim/v2/Users", headers=scim_headers, json=user_data)
    assert res2.status_code == 409
    assert "uniqueness" in res2.json().get("scimType", "")


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, scim_headers: dict) -> None:
    """GET /scim/v2/Users/{id} returns a single SCIM User."""
    # Create a user first
    create_res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "getme@example.com",
            "name": {"givenName": "Get", "familyName": "Me"},
            "active": True,
        },
    )
    user_id = create_res.json()["id"]

    res = await client.get(f"/scim/v2/Users/{user_id}", headers=scim_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == user_id
    assert data["userName"] == "getme@example.com"


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient, scim_headers: dict) -> None:
    """GET /scim/v2/Users/{id} returns 404 for unknown user."""
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/scim/v2/Users/{fake_id}", headers=scim_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, scim_headers: dict) -> None:
    """GET /scim/v2/Users returns a SCIM ListResponse."""
    # Create some users
    for i in range(3):
        await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": f"listuser{i}@example.com",
                "name": {"givenName": f"User{i}", "familyName": "List"},
                "active": True,
            },
        )

    res = await client.get("/scim/v2/Users", headers=scim_headers)
    assert res.status_code == 200
    data = res.json()
    assert "urn:ietf:params:scim:api:messages:2.0:ListResponse" in data["schemas"]
    # At least 3 SCIM-created users + the initial registered user
    assert data["totalResults"] >= 3
    assert len(data["Resources"]) >= 3
    assert data["startIndex"] == 1


@pytest.mark.asyncio
async def test_replace_user(client: AsyncClient, scim_headers: dict) -> None:
    """PUT /scim/v2/Users/{id} replaces user data."""
    create_res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "replace-me@example.com",
            "name": {"givenName": "Old", "familyName": "Name"},
            "active": True,
        },
    )
    user_id = create_res.json()["id"]

    res = await client.put(
        f"/scim/v2/Users/{user_id}",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "replace-me@example.com",
            "name": {"givenName": "New", "familyName": "Name"},
            "displayName": "New Name",
            "active": True,
            "externalId": "ext-replaced",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["displayName"] == "New Name"
    assert data["externalId"] == "ext-replaced"


@pytest.mark.asyncio
async def test_patch_user_active(client: AsyncClient, scim_headers: dict) -> None:
    """PATCH /scim/v2/Users/{id} can set active=false (deprovisioning)."""
    create_res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "patch-me@example.com",
            "name": {"givenName": "Patch", "familyName": "Me"},
            "active": True,
        },
    )
    user_id = create_res.json()["id"]

    res = await client.patch(
        f"/scim/v2/Users/{user_id}",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "active", "value": False},
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["active"] is False


@pytest.mark.asyncio
async def test_patch_user_display_name(client: AsyncClient, scim_headers: dict) -> None:
    """PATCH /scim/v2/Users/{id} can update displayName."""
    create_res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "patch-name@example.com",
            "name": {"givenName": "Original", "familyName": "Name"},
            "active": True,
        },
    )
    user_id = create_res.json()["id"]

    res = await client.patch(
        f"/scim/v2/Users/{user_id}",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "displayName", "value": "Updated Name"},
            ],
        },
    )
    assert res.status_code == 200
    assert res.json()["displayName"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, scim_headers: dict) -> None:
    """DELETE /scim/v2/Users/{id} soft-deletes (deactivates) the user."""
    create_res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "delete-me@example.com",
            "name": {"givenName": "Delete", "familyName": "Me"},
            "active": True,
        },
    )
    user_id = create_res.json()["id"]

    res = await client.delete(f"/scim/v2/Users/{user_id}", headers=scim_headers)
    assert res.status_code == 204

    # Verify user is deactivated, not hard-deleted
    get_res = await client.get(f"/scim/v2/Users/{user_id}", headers=scim_headers)
    assert get_res.status_code == 200
    assert get_res.json()["active"] is False


@pytest.mark.asyncio
async def test_filter_by_username(client: AsyncClient, scim_headers: dict) -> None:
    """GET /scim/v2/Users?filter=userName eq "x" returns matching users."""
    target_email = "filter-target@example.com"
    await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": target_email,
            "name": {"givenName": "Filter", "familyName": "Target"},
            "active": True,
        },
    )
    # Create a non-matching user
    await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "other@example.com",
            "name": {"givenName": "Other", "familyName": "User"},
            "active": True,
        },
    )

    res = await client.get(
        "/scim/v2/Users",
        headers=scim_headers,
        params={"filter": f'userName eq "{target_email}"'},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["userName"] == target_email


@pytest.mark.asyncio
async def test_filter_by_external_id(client: AsyncClient, scim_headers: dict) -> None:
    """GET /scim/v2/Users?filter=externalId eq "x" works."""
    await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "ext-filter@example.com",
            "name": {"givenName": "Ext", "familyName": "Filter"},
            "externalId": "unique-ext-123",
            "active": True,
        },
    )

    res = await client.get(
        "/scim/v2/Users",
        headers=scim_headers,
        params={"filter": 'externalId eq "unique-ext-123"'},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["externalId"] == "unique-ext-123"


@pytest.mark.asyncio
async def test_scim_pagination(client: AsyncClient, scim_headers: dict) -> None:
    """SCIM pagination with startIndex and count works correctly."""
    # Create 5 users
    for i in range(5):
        await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": f"page-user-{i}@example.com",
                "name": {"givenName": f"Page{i}", "familyName": "User"},
                "active": True,
            },
        )

    # Request page of 2 starting at index 1
    res = await client.get(
        "/scim/v2/Users",
        headers=scim_headers,
        params={"startIndex": 1, "count": 2},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["itemsPerPage"] == 2
    assert len(data["Resources"]) == 2
    assert data["startIndex"] == 1
    # totalResults includes the original registered user + 5 SCIM users
    assert data["totalResults"] >= 5

    # Request second page
    res2 = await client.get(
        "/scim/v2/Users",
        headers=scim_headers,
        params={"startIndex": 3, "count": 2},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["Resources"]) == 2
    assert data2["startIndex"] == 3

    # The user IDs on page 1 and page 2 should be different
    page1_ids = {r["id"] for r in data["Resources"]}
    page2_ids = {r["id"] for r in data2["Resources"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_create_user_minimal(client: AsyncClient, scim_headers: dict) -> None:
    """POST /scim/v2/Users with only userName should work."""
    res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "minimal@example.com",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["userName"] == "minimal@example.com"
    assert data["active"] is True


@pytest.mark.asyncio
async def test_patch_user_no_path_value_dict(client: AsyncClient, scim_headers: dict) -> None:
    """PATCH with no path and value as a dict updates multiple attributes."""
    create_res = await client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "multi-patch@example.com",
            "name": {"givenName": "Multi", "familyName": "Patch"},
            "active": True,
        },
    )
    user_id = create_res.json()["id"]

    res = await client.patch(
        f"/scim/v2/Users/{user_id}",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "value": {
                        "active": False,
                        "displayName": "Patched Multi",
                    },
                },
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["active"] is False
    assert data["displayName"] == "Patched Multi"


@pytest.mark.asyncio
async def test_scim_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db: AsyncSession,
) -> None:
    """SCIM token for tenant A should not see users from tenant B."""
    # Create SCIM token for first tenant
    tenant_a_id, user_a_id = await _get_tenant_and_user(db, "usera@test.com")
    token_a = await _create_scim_token(db, tenant_a_id, user_a_id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create SCIM token for second tenant
    tenant_b_id, user_b_id = await _get_tenant_and_user(db, "userb@test.com")
    token_b = await _create_scim_token(db, tenant_b_id, user_b_id)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create user in tenant A
    res_a = await client.post(
        "/scim/v2/Users",
        headers=headers_a,
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "tenant-a-user@example.com",
            "name": {"givenName": "TenantA", "familyName": "User"},
            "active": True,
        },
    )
    assert res_a.status_code == 201
    user_a_scim_id = res_a.json()["id"]

    # Tenant B should not see tenant A's user
    res_b = await client.get(f"/scim/v2/Users/{user_a_scim_id}", headers=headers_b)
    assert res_b.status_code == 404

    # Tenant B's user list should not include tenant A's SCIM user
    list_b = await client.get("/scim/v2/Users", headers=headers_b)
    b_emails = [r["userName"] for r in list_b.json()["Resources"]]
    assert "tenant-a-user@example.com" not in b_emails
