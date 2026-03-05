from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["error"] is None

    summary = data["data"]
    assert "secure_score" in summary
    assert "total_assets" in summary
    assert "total_findings" in summary
    assert "findings_by_severity" in summary
    assert "top_failing_controls" in summary
    assert "assets_by_type" in summary

    assert summary["total_assets"] >= 1
    assert summary["total_findings"] >= 1
    assert isinstance(summary["findings_by_severity"], dict)
    assert isinstance(summary["assets_by_type"], dict)


@pytest.mark.asyncio
async def test_dashboard_summary_empty(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    summary = res.json()["data"]
    assert summary["total_assets"] == 0
    assert summary["total_findings"] == 0
    assert summary["findings_by_severity"] == {}
    assert summary["assets_by_type"] == {}
    assert summary["top_failing_controls"] == []


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/dashboard/summary")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_severity_counts(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    severity_counts = res.json()["data"]["findings_by_severity"]
    # Our seed data has one "high" severity finding with status "fail"
    assert severity_counts.get("high", 0) >= 1


@pytest.mark.asyncio
async def test_dashboard_top_failing_controls(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    top = res.json()["data"]["top_failing_controls"]
    assert len(top) >= 1
    control = top[0]
    assert "code" in control
    assert "name" in control
    assert "severity" in control
    assert "fail_count" in control
    assert "total_count" in control
    assert control["fail_count"] >= 1


@pytest.mark.asyncio
async def test_dashboard_tenant_isolation(client: AsyncClient, second_auth_headers: dict, seed_data: dict) -> None:
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    res = await client.get("/api/v1/dashboard/summary", headers=second_auth_headers)
    assert res.status_code == 200
    summary = res.json()["data"]
    assert summary["total_assets"] == 0
    assert summary["total_findings"] == 0


# ── Cross-Cloud endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_cloud_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/dashboard/cross-cloud")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_cross_cloud_empty(client: AsyncClient, auth_headers: dict) -> None:
    """With no cloud accounts, the endpoint returns an empty summary."""
    res = await client.get("/api/v1/dashboard/cross-cloud", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["error"] is None
    summary = data["data"]
    assert summary["providers"] == []
    assert summary["totals"]["accounts"] == 0
    assert summary["totals"]["assets"] == 0
    assert summary["totals"]["findings"] == 0
    assert summary["totals"]["overall_score"] is None
    assert summary["comparison"]["best_provider"] is None
    assert summary["comparison"]["worst_provider"] is None
    assert summary["comparison"]["score_gap"] == 0.0


@pytest.mark.asyncio
async def test_cross_cloud_with_data(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    """With seed data (single Azure account), the cross-cloud endpoint
    returns one provider with correct aggregation."""
    res = await client.get("/api/v1/dashboard/cross-cloud", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["error"] is None

    summary = data["data"]
    assert len(summary["providers"]) == 1

    azure = summary["providers"][0]
    assert azure["provider"] == "azure"
    assert azure["display_name"] == "Azure"
    assert azure["accounts_count"] == 1
    assert azure["total_assets"] >= 1
    assert azure["total_findings"] >= 1
    assert isinstance(azure["findings_by_severity"], dict)
    assert azure["trend"] in ("improving", "stable", "declining")

    # Totals should match the single provider
    totals = summary["totals"]
    assert totals["accounts"] == azure["accounts_count"]
    assert totals["assets"] == azure["total_assets"]
    assert totals["findings"] == azure["total_findings"]

    # With a single provider, comparison should point to itself
    comparison = summary["comparison"]
    if comparison["best_provider"] is not None:
        assert comparison["best_provider"] == "azure"
        assert comparison["score_gap"] == 0.0


@pytest.mark.asyncio
async def test_cross_cloud_tenant_isolation(client: AsyncClient, second_auth_headers: dict, seed_data: dict) -> None:
    """Second tenant should not see first tenant's data."""
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    res = await client.get("/api/v1/dashboard/cross-cloud", headers=second_auth_headers)
    assert res.status_code == 200
    summary = res.json()["data"]
    assert summary["providers"] == []
    assert summary["totals"]["accounts"] == 0
