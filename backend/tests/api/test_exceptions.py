from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_exception(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    finding_id = seed_data["finding_id"]
    res = await client.post(
        f"/api/v1/findings/{finding_id}/exception",
        headers=auth_headers,
        json={"reason": "Accepted risk for this finding"},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["status"] == "requested"
    assert data["finding_id"] == finding_id


@pytest.mark.asyncio
async def test_create_exception_finding_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"/api/v1/findings/{fake_id}/exception",
        headers=auth_headers,
        json={"reason": "test"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_exception_conflict(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    finding_id = seed_data["finding_id"]
    # First exception
    await client.post(
        f"/api/v1/findings/{finding_id}/exception",
        headers=auth_headers,
        json={"reason": "First"},
    )
    # Second should conflict
    res = await client.post(
        f"/api/v1/findings/{finding_id}/exception",
        headers=auth_headers,
        json={"reason": "Second"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_list_exceptions(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    finding_id = seed_data["finding_id"]
    await client.post(
        f"/api/v1/findings/{finding_id}/exception",
        headers=auth_headers,
        json={"reason": "Test reason"},
    )

    res = await client.get("/api/v1/exceptions", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] >= 1


@pytest.mark.asyncio
async def test_approve_exception_self_blocked(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    """Same user cannot approve their own waiver request (separation of duties)."""
    finding_id = seed_data["finding_id"]
    client.cookies.clear()
    create_res = await client.post(
        f"/api/v1/findings/{finding_id}/exception",
        headers=auth_headers,
        json={"reason": "Self-approval test"},
    )
    exc_id = create_res.json()["data"]["id"]

    client.cookies.clear()
    res = await client.put(f"/api/v1/exceptions/{exc_id}/approve", headers=auth_headers)
    assert res.status_code == 403
    assert "Cannot approve your own" in res.json()["detail"]


@pytest.mark.asyncio
async def test_reject_exception(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    finding_id = seed_data["finding_id"]
    create_res = await client.post(
        f"/api/v1/findings/{finding_id}/exception",
        headers=auth_headers,
        json={"reason": "Rejected test"},
    )
    exc_id = create_res.json()["data"]["id"]

    res = await client.put(f"/api/v1/exceptions/{exc_id}/reject", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_exception_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/exceptions")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_bulk_waive_self_approval_blocked(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    """Regression (M1 / BL-02↔BL-03): an exception created via bulk-waive must
    still be subject to separation-of-duties. Previously bulk-waive left
    requested_by NULL, so the requester could approve their own waiver."""
    finding_id = seed_data["finding_id"]
    client.cookies.clear()

    bulk = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": [finding_id], "reason": "bulk self-approval test"},
    )
    assert bulk.status_code == 200
    assert bulk.json()["data"]["processed"] == 1

    client.cookies.clear()
    listed = await client.get("/api/v1/exceptions", headers=auth_headers)
    exc_id = listed.json()["data"][0]["id"]

    client.cookies.clear()
    res = await client.put(f"/api/v1/exceptions/{exc_id}/approve", headers=auth_headers)
    assert res.status_code == 403
    assert "Cannot approve your own" in res.json()["detail"]
