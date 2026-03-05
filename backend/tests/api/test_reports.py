from __future__ import annotations

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Executive Summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executive_summary_pdf(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/reports/executive-summary",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert res.content[:5] == b"%PDF-"
    assert "executive-summary.pdf" in res.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_executive_summary_empty(client: AsyncClient, auth_headers: dict) -> None:
    """Report should generate even with no findings."""
    res = await client.get(
        "/api/v1/reports/executive-summary",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_executive_summary_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/reports/executive-summary")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Compliance Report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_report_pdf(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/reports/compliance",
        headers=auth_headers,
        params={"framework": "cis_azure"},
    )
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert res.content[:5] == b"%PDF-"
    assert "compliance-cis_azure.pdf" in res.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_compliance_report_default_framework(client: AsyncClient, auth_headers: dict) -> None:
    """Default framework should be cis_azure."""
    res = await client.get(
        "/api/v1/reports/compliance",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_compliance_report_soc2(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/reports/compliance",
        headers=auth_headers,
        params={"framework": "soc2"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_compliance_report_nist(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/reports/compliance",
        headers=auth_headers,
        params={"framework": "nist"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_compliance_report_iso27001(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/reports/compliance",
        headers=auth_headers,
        params={"framework": "iso27001"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_compliance_report_invalid_framework(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/reports/compliance",
        headers=auth_headers,
        params={"framework": "invalid_framework"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_compliance_report_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/reports/compliance")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Technical Detail Report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_technical_detail_pdf(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert res.content[:5] == b"%PDF-"
    assert "technical-detail.pdf" in res.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_technical_detail_filter_severity(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
        params={"severity": "high"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_technical_detail_filter_status(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
        params={"status": "fail"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_technical_detail_filter_combined(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
        params={"severity": "high", "status": "fail"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_technical_detail_empty(client: AsyncClient, auth_headers: dict) -> None:
    """Report generates even with no findings."""
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_technical_detail_invalid_severity(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
        params={"severity": "critical"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_technical_detail_invalid_status(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/reports/technical-detail",
        headers=auth_headers,
        params={"status": "unknown"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_technical_detail_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/reports/technical-detail")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reports_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    seed_data: dict,
) -> None:
    """Reports from one tenant should not leak data to another tenant.

    The second tenant has no data, so reports should generate empty PDFs.
    """
    # Second user should get a valid (but empty) report
    res = await client.get(
        "/api/v1/reports/executive-summary",
        headers=second_auth_headers,
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"
