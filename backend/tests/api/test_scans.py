from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_scan(client: AsyncClient, auth_headers: dict, make_account) -> None:
    account = await make_account("Scan Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        res = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
    assert res.status_code == 201
    data = res.json()
    assert data["error"] is None
    assert data["data"]["status"] == "pending"
    assert data["data"]["scan_type"] == "full"
    assert data["data"]["cloud_account_id"] == account["id"]


@pytest.mark.asyncio
async def test_create_scan_requires_auth(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/scans",
        json={"cloud_account_id": str(uuid.uuid4())},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_scan_account_not_found(
    client: AsyncClient, auth_headers: dict
) -> None:
    res = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_scan_conflict(
    client: AsyncClient, auth_headers: dict, make_account
) -> None:
    account = await make_account("Conflict Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        # First scan succeeds
        res1 = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
        assert res1.status_code == 201

        # Second scan conflicts
        res2 = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_get_scan(client: AsyncClient, auth_headers: dict, make_account) -> None:
    account = await make_account("Get Scan Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        create_res = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
    scan_id = create_res.json()["data"]["id"]

    res = await client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"]["id"] == scan_id


@pytest.mark.asyncio
async def test_get_scan_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/scans/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_scan_tenant_isolation(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, make_account
) -> None:
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    account = await make_account("Isolation Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        create_res = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
    scan_id = create_res.json()["data"]["id"]

    # Clear cookies again before tenant B request
    client.cookies.clear()

    # User B cannot see User A's scan
    res = await client.get(f"/api/v1/scans/{scan_id}", headers=second_auth_headers)
    assert res.status_code == 404
