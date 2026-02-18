from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_assets(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get("/api/v1/assets", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["error"] is None
    assert data["meta"]["total"] >= 1
    assert len(data["data"]) >= 1

    asset = data["data"][0]
    assert "name" in asset
    assert "resource_type" in asset
    assert "region" in asset
    assert "last_seen_at" in asset


@pytest.mark.asyncio
async def test_list_assets_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/assets")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_assets_filter_by_type(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    res = await client.get(
        "/api/v1/assets",
        headers=auth_headers,
        params={"resource_type": "Microsoft.Compute/virtualMachines"},
    )
    assert res.status_code == 200
    for asset in res.json()["data"]:
        assert asset["resource_type"] == "Microsoft.Compute/virtualMachines"


@pytest.mark.asyncio
async def test_list_assets_filter_by_region(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    res = await client.get(
        "/api/v1/assets",
        headers=auth_headers,
        params={"region": "westeurope"},
    )
    assert res.status_code == 200
    for asset in res.json()["data"]:
        assert asset["region"] == "westeurope"


@pytest.mark.asyncio
async def test_get_asset(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    asset_id = seed_data["asset_id"]
    res = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "vm-test-01"


@pytest.mark.asyncio
async def test_get_asset_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/assets/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_assets_tenant_isolation(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, seed_data: dict
) -> None:
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    # User B shouldn't see User A's assets
    res = await client.get("/api/v1/assets", headers=second_auth_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 0

    # Direct access also blocked
    asset_id = seed_data["asset_id"]
    res = await client.get(f"/api/v1/assets/{asset_id}", headers=second_auth_headers)
    assert res.status_code == 404
