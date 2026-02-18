from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_account(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "My Subscription",
            "provider_account_id": "sub-12345",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["error"] is None
    assert data["data"]["display_name"] == "My Subscription"
    assert data["data"]["provider"] == "azure"
    assert data["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_create_account_requires_auth(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/accounts",
        json={
            "provider": "azure",
            "display_name": "No Auth",
            "provider_account_id": "sub-xxx",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_accounts(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Account A",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Account B",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )

    res = await client.get("/api/v1/accounts", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 2


@pytest.mark.asyncio
async def test_list_accounts_with_pagination(
    client: AsyncClient, auth_headers: dict
) -> None:
    # Create 3 accounts
    for i in range(3):
        await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "provider": "azure",
                "display_name": f"Account {i}",
                "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
                "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
            },
        )

    res = await client.get(
        "/api/v1/accounts", headers=auth_headers, params={"page": 1, "size": 2}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["meta"]["total"] == 3
    assert data["meta"]["page"] == 1
    assert data["meta"]["size"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_get_account(client: AsyncClient, auth_headers: dict) -> None:
    create_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Get Me",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    account_id = create_res.json()["data"]["id"]

    res = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"]["display_name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_account_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/accounts/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient, auth_headers: dict) -> None:
    create_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Delete Me",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    account_id = create_res.json()["data"]["id"]

    res = await client.delete(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert res.status_code == 204

    # Verify it's gone
    get_res = await client.get(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict
) -> None:
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    # User A creates an account
    create_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "User A Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    account_id = create_res.json()["data"]["id"]

    # Clear cookies again before tenant B request
    client.cookies.clear()

    # User B cannot see it
    res = await client.get(f"/api/v1/accounts/{account_id}", headers=second_auth_headers)
    assert res.status_code == 404

    # User B list doesn't include it
    list_res = await client.get("/api/v1/accounts", headers=second_auth_headers)
    assert list_res.status_code == 200
    ids = [a["id"] for a in list_res.json()["data"]]
    assert account_id not in ids
