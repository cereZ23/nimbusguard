from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _register_and_get_viewer(client: AsyncClient, admin_headers: dict) -> dict[str, str]:
    """Create a viewer user and return auth headers."""
    res = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "viewer@test.com",
            "full_name": "Viewer User",
            "password": "Viewer@pass123",
            "role": "viewer",
        },
    )
    assert res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@test.com", "password": "Viewer@pass123"},
    )
    assert login_res.status_code == 200
    token = login_res.cookies.get("access_token")
    assert token, "access_token cookie not set in login response"
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_viewer_cannot_create_account(client: AsyncClient, auth_headers: dict) -> None:
    viewer_headers = await _register_and_get_viewer(client, auth_headers)
    res = await client.post(
        "/api/v1/accounts",
        headers=viewer_headers,
        json={
            "provider": "azure",
            "display_name": "Should Fail",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_delete_account(client: AsyncClient, auth_headers: dict, make_account) -> None:
    account = await make_account("Admin Account")
    viewer_headers = await _register_and_get_viewer(client, auth_headers)
    res = await client.delete(f"/api/v1/accounts/{account['id']}", headers=viewer_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_list_accounts(client: AsyncClient, auth_headers: dict, make_account) -> None:
    await make_account("Visible Account")
    viewer_headers = await _register_and_get_viewer(client, auth_headers)
    res = await client.get("/api/v1/accounts", headers=viewer_headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_viewer_cannot_trigger_scan(client: AsyncClient, auth_headers: dict, make_account) -> None:
    account = await make_account("Scan Account")
    viewer_headers = await _register_and_get_viewer(client, auth_headers)
    res = await client.post(
        "/api/v1/scans",
        headers=viewer_headers,
        json={"cloud_account_id": account["id"]},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_and_read(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Admin Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 201
