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
async def test_list_accounts_with_pagination(client: AsyncClient, auth_headers: dict) -> None:
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

    res = await client.get("/api/v1/accounts", headers=auth_headers, params={"page": 1, "size": 2})
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
async def test_tenant_isolation(client: AsyncClient, auth_headers: dict, second_auth_headers: dict) -> None:
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


# ── Microsoft 365 provider ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_m365_account(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "m365",
            "display_name": "Contoso M365",
            "provider_account_id": "11111111-2222-3333-4444-555555555555",
            "credentials": {
                "tenant_id": "11111111-2222-3333-4444-555555555555",
                "client_id": "c",
                "client_secret": "s",
            },
        },
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["provider"] == "m365"
    assert data["display_name"] == "Contoso M365"


@pytest.mark.asyncio
async def test_create_m365_account_missing_credentials(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "m365",
            "display_name": "Broken",
            "provider_account_id": "tid",
            "credentials": {"tenant_id": "tid"},
        },
    )
    assert res.status_code == 422
    assert "client_id" in res.text


@pytest.mark.asyncio
async def test_create_account_unknown_provider_rejected(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "gcp",
            "display_name": "Nope",
            "provider_account_id": "x",
            "credentials": {"anything": "y"},
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_m365_test_connection_reports_workload_warnings(
    client: AsyncClient, auth_headers: dict, monkeypatch
) -> None:
    """Graph baseline works, SharePoint is forbidden, Exchange role missing —
    the response succeeds with per-workload warnings."""
    import app.services.m365.exchange_client as exchange_module
    import app.services.m365.graph_client as graph_module

    class _FakeGraph:
        def __init__(self, tenant_id, client_id, client_secret):
            pass

        def authenticate(self):
            return True

        async def get_json(self, path, extra_headers=None):
            if path.startswith("/organization"):
                return 200, {"value": [{"displayName": "Contoso"}]}
            if path.startswith("/admin/sharepoint"):
                return 403, None
            return 200, {"value": []}

    class _FakeExchange:
        def __init__(self, tenant_id, client_id, client_secret):
            pass

        def authenticate(self):
            return False

    monkeypatch.setattr(graph_module, "M365GraphClient", _FakeGraph)
    monkeypatch.setattr(exchange_module, "ExchangeAdminClient", _FakeExchange)

    res = await client.post(
        "/api/v1/accounts/test-connection",
        headers=auth_headers,
        json={"provider": "m365", "tenant_id": "tid", "client_id": "cid", "client_secret": "sec"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is True
    assert "Contoso" in data["message"]
    assert any("SharePointTenantSettings" in w for w in data["warnings"])
    assert any("Exchange.ManageAsApp" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_m365_test_connection_invalid_credentials(client: AsyncClient, auth_headers: dict, monkeypatch) -> None:
    import app.services.m365.graph_client as graph_module

    class _FailingGraph:
        def __init__(self, tenant_id, client_id, client_secret):
            pass

        def authenticate(self):
            return False

    monkeypatch.setattr(graph_module, "M365GraphClient", _FailingGraph)

    res = await client.post(
        "/api/v1/accounts/test-connection",
        headers=auth_headers,
        json={"provider": "m365", "tenant_id": "tid", "client_id": "cid", "client_secret": "bad"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is False


@pytest.mark.asyncio
async def test_m365_test_connection_requires_fields(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/accounts/test-connection",
        headers=auth_headers,
        json={"provider": "m365", "tenant_id": "tid"},
    )
    assert res.status_code == 422
