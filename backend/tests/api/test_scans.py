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
async def test_create_scan_account_not_found(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_scan_conflict(client: AsyncClient, auth_headers: dict, make_account) -> None:
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


# ── GET /scans list endpoint ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_scans_empty(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get("/api/v1/scans", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["page"] == 1
    assert body["meta"]["size"] == 20


@pytest.mark.asyncio
async def test_list_scans_requires_auth(client: AsyncClient) -> None:
    client.cookies.clear()
    res = await client.get("/api/v1/scans")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_scans_returns_created_scan(
    client: AsyncClient, auth_headers: dict, make_account
) -> None:
    account = await make_account("List Scans Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        create_res = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
    assert create_res.status_code == 201
    scan_id = create_res.json()["data"]["id"]

    list_res = await client.get("/api/v1/scans", headers=auth_headers)
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["meta"]["total"] >= 1
    ids = [item["id"] for item in body["data"]]
    assert scan_id in ids

    # Enriched fields should be present.
    scan_item = next(item for item in body["data"] if item["id"] == scan_id)
    assert scan_item["cloud_account_name"] == "List Scans Account"
    assert scan_item["cloud_account_provider"] in {"azure", "aws"}
    assert "duration_seconds" in scan_item
    assert "findings_count" in scan_item
    assert scan_item["findings_count"] == 0
    assert scan_item["findings_fail_count"] == 0
    assert scan_item["findings_pass_count"] == 0


@pytest.mark.asyncio
async def test_list_scans_filter_by_account(
    client: AsyncClient, auth_headers: dict, make_account
) -> None:
    account_a = await make_account("Account A")
    account_b = await make_account("Account B")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account_a["id"]},
        )
        await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account_b["id"]},
        )

    res_a = await client.get(
        "/api/v1/scans",
        headers=auth_headers,
        params={"cloud_account_id": account_a["id"]},
    )
    assert res_a.status_code == 200
    body_a = res_a.json()
    assert body_a["meta"]["total"] >= 1
    for item in body_a["data"]:
        assert item["cloud_account_id"] == account_a["id"]


@pytest.mark.asyncio
async def test_list_scans_filter_by_status(
    client: AsyncClient, auth_headers: dict, make_account
) -> None:
    account = await make_account("Status Filter Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )

    # Newly created scan is in status "pending".
    res_pending = await client.get(
        "/api/v1/scans",
        headers=auth_headers,
        params={"status": "pending"},
    )
    assert res_pending.status_code == 200
    assert all(item["status"] == "pending" for item in res_pending.json()["data"])

    # Filter with a status that won't match anything.
    res_completed = await client.get(
        "/api/v1/scans",
        headers=auth_headers,
        params={"status": "completed"},
    )
    assert res_completed.status_code == 200
    assert all(item["status"] == "completed" for item in res_completed.json()["data"])


@pytest.mark.asyncio
async def test_list_scans_pagination(
    client: AsyncClient, auth_headers: dict, make_account
) -> None:
    account = await make_account("Pagination Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        create_res = await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )
        assert create_res.status_code == 201

    res = await client.get(
        "/api/v1/scans",
        headers=auth_headers,
        params={"page": 1, "size": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["page"] == 1
    assert body["meta"]["size"] == 5
    assert len(body["data"]) <= 5


@pytest.mark.asyncio
async def test_list_scans_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    make_account,
) -> None:
    client.cookies.clear()
    account = await make_account("Isolation List Account")

    with patch("app.worker.tasks.run_scan") as mock_task:
        mock_task.delay.return_value = None
        await client.post(
            "/api/v1/scans",
            headers=auth_headers,
            json={"cloud_account_id": account["id"]},
        )

    client.cookies.clear()
    # Tenant B should not see any of tenant A's scans.
    res = await client.get("/api/v1/scans", headers=second_auth_headers)
    assert res.status_code == 200
    body = res.json()
    for item in body["data"]:
        assert item["cloud_account_id"] != account["id"]
