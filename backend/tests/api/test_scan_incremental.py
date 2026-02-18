"""Tests for incremental scan creation and scan_type handling."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_incremental_scan(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    account_id = seed_data["account_id"]
    res = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": account_id, "scan_type": "incremental"},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["scan_type"] == "incremental"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_full_scan(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    account_id = seed_data["account_id"]
    res = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": account_id, "scan_type": "full"},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["scan_type"] == "full"


@pytest.mark.asyncio
async def test_scan_default_type_is_full(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    account_id = seed_data["account_id"]
    res = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": account_id},
    )
    assert res.status_code == 201
    assert res.json()["data"]["scan_type"] == "full"


@pytest.mark.asyncio
async def test_concurrent_scan_conflict(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    account_id = seed_data["account_id"]
    # First scan
    res1 = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": account_id, "scan_type": "full"},
    )
    assert res1.status_code == 201

    # Second scan should conflict (first is still pending)
    res2 = await client.post(
        "/api/v1/scans",
        headers=auth_headers,
        json={"cloud_account_id": account_id, "scan_type": "incremental"},
    )
    assert res2.status_code == 409
