from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_controls(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get("/api/v1/controls", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["meta"]["total"] >= 1
    ctrl = data["data"][0]
    assert "code" in ctrl
    assert "name" in ctrl
    assert "pass_count" in ctrl
    assert "fail_count" in ctrl
    assert "total_count" in ctrl


@pytest.mark.asyncio
async def test_list_controls_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/controls")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_control(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    control_id = seed_data["control_id"]
    res = await client.get(f"/api/v1/controls/{control_id}", headers=auth_headers)
    assert res.status_code == 200
    ctrl = res.json()["data"]
    assert ctrl["id"] == control_id
    assert ctrl["total_count"] >= 1


@pytest.mark.asyncio
async def test_get_control_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/controls/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_control_findings(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    control_id = seed_data["control_id"]
    res = await client.get(f"/api/v1/controls/{control_id}/findings", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] >= 1


@pytest.mark.asyncio
async def test_dashboard_trend(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/dashboard/trend",
        headers=auth_headers,
        params={"period": "30d"},
    )
    assert res.status_code == 200
    trend = res.json()["data"]
    assert "data" in trend
    assert trend["period"] == "30d"


@pytest.mark.asyncio
async def test_dashboard_trend_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/dashboard/trend")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_controls_filter_by_framework(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    """Controls endpoint should accept any framework filter without error."""
    for framework in ("cis-lite", "soc2", "nist", "iso27001"):
        res = await client.get(
            "/api/v1/controls",
            headers=auth_headers,
            params={"framework": framework},
        )
        assert res.status_code == 200, f"Expected 200 for framework={framework}"
        data = res.json()
        assert data["error"] is None
        assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_list_controls_iso27001_returns_only_mapped_controls(
    client: AsyncClient, auth_headers: dict, db: object
) -> None:
    """Controls without iso27001 mapping should not appear in the iso27001 view."""
    res = await client.get(
        "/api/v1/controls",
        headers=auth_headers,
        params={"framework": "iso27001", "size": 200},
    )
    assert res.status_code == 200
    for ctrl in res.json()["data"]:
        assert "iso27001" in (ctrl.get("framework_mappings") or {}), (
            f"Control {ctrl['code']} returned but has no iso27001 mapping"
        )
