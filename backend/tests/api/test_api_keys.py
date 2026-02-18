from __future__ import annotations

import hashlib
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "CI Key", "scopes": ["read"]},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["error"] is None
    assert data["data"]["name"] == "CI Key"
    assert data["data"]["scopes"] == ["read"]
    assert data["data"]["is_active"] is True
    # Full key returned at creation
    assert data["data"]["api_key"].startswith("cspm_")
    assert data["data"]["key_prefix"] == data["data"]["api_key"][:8]


@pytest.mark.asyncio
async def test_create_api_key_requires_auth(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "CI Key", "scopes": ["read"]},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_api_key_invalid_scope(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Bad Key", "scopes": ["invalid"]},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_empty_scopes(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Bad Key", "scopes": []},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_empty_name(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "", "scopes": ["read"]},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_with_expiry(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Expiring Key", "scopes": ["read"], "expires_in_days": 30},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_create_api_key_without_expiry(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Permanent Key", "scopes": ["read"]},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient, auth_headers: dict) -> None:
    # Create two keys
    await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Key 1", "scopes": ["read"]},
    )
    await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Key 2", "scopes": ["read", "write"]},
    )

    res = await client.get("/api/v1/api-keys", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 2

    # Full key should NOT be in list response
    for key in data["data"]:
        assert "api_key" not in key


@pytest.mark.asyncio
async def test_list_api_keys_does_not_expose_full_key(
    client: AsyncClient, auth_headers: dict
) -> None:
    create_res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Secret Key", "scopes": ["read"]},
    )
    full_key = create_res.json()["data"]["api_key"]

    list_res = await client.get("/api/v1/api-keys", headers=auth_headers)
    for key in list_res.json()["data"]:
        # The list endpoint uses ApiKeyResponse (no api_key field)
        assert full_key not in str(key)


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient, auth_headers: dict) -> None:
    create_res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "To Revoke", "scopes": ["read"]},
    )
    key_id = create_res.json()["data"]["id"]

    res = await client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers)
    assert res.status_code == 204

    # Verify it is gone
    list_res = await client.get("/api/v1/api-keys", headers=auth_headers)
    assert len(list_res.json()["data"]) == 0


@pytest.mark.asyncio
async def test_revoke_api_key_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.delete(f"/api/v1/api-keys/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_authenticate_with_api_key(client: AsyncClient, auth_headers: dict) -> None:
    """Create an API key and use it to access a protected endpoint."""
    create_res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Auth Test Key", "scopes": ["read"]},
    )
    full_key = create_res.json()["data"]["api_key"]

    # Use the API key to access a protected endpoint
    res = await client.get(
        "/api/v1/assets",
        headers={"Authorization": f"Bearer {full_key}"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_authenticate_with_revoked_api_key(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Revoked API key should be rejected."""
    create_res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Revoked Key", "scopes": ["read"]},
    )
    full_key = create_res.json()["data"]["api_key"]
    key_id = create_res.json()["data"]["id"]

    # Revoke it
    await client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers)

    # Clear cookies so the revoked API key is the only credential
    client.cookies.clear()

    # Try to use it
    res = await client.get(
        "/api/v1/assets",
        headers={"Authorization": f"Bearer {full_key}"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_with_invalid_api_key(client: AsyncClient) -> None:
    """Invalid API key should be rejected."""
    res = await client.get(
        "/api/v1/assets",
        headers={"Authorization": "Bearer cspm_invalidkey1234567890abcdef"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_api_key_multiple_scopes(
    client: AsyncClient, auth_headers: dict
) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Full Access", "scopes": ["read", "write", "scan"]},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert sorted(data["scopes"]) == ["read", "scan", "write"]


@pytest.mark.asyncio
async def test_create_api_key_default_scopes(
    client: AsyncClient, auth_headers: dict
) -> None:
    """If scopes not specified, defaults to ['read']."""
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Default Scopes"},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["scopes"] == ["read"]


@pytest.mark.asyncio
async def test_create_api_key_expiry_too_long(
    client: AsyncClient, auth_headers: dict
) -> None:
    res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Too Long", "scopes": ["read"], "expires_in_days": 400},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_api_key_hash_is_sha256(client: AsyncClient, auth_headers: dict) -> None:
    """Verify the key hash stored corresponds to SHA-256 of the full key."""
    from sqlalchemy import select

    from app.models.api_key import ApiKey
    from tests.conftest import TestSession

    create_res = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "Hash Test", "scopes": ["read"]},
    )
    full_key = create_res.json()["data"]["api_key"]
    key_id = create_res.json()["data"]["id"]

    expected_hash = hashlib.sha256(full_key.encode()).hexdigest()

    async with TestSession() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        record = result.scalar_one()
        assert record.key_hash == expected_hash
