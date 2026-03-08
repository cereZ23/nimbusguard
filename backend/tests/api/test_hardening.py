"""Tests for security hardening fixes (pagination bounds, LIKE escape, security headers, MFA brute-force)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── Pagination bounds ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_findings_pagination_size_over_max(client: AsyncClient, auth_headers: dict) -> None:
    """size > 100 should be rejected with 422."""
    res = await client.get("/api/v1/findings?size=999", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_findings_pagination_size_zero(client: AsyncClient, auth_headers: dict) -> None:
    """size=0 should be rejected with 422."""
    res = await client.get("/api/v1/findings?size=0", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_findings_pagination_page_zero(client: AsyncClient, auth_headers: dict) -> None:
    """page=0 should be rejected with 422."""
    res = await client.get("/api/v1/findings?page=0", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_assets_pagination_size_over_max(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get("/api/v1/assets?size=200", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_accounts_pagination_size_over_max(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get("/api/v1/accounts?size=200", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_controls_pagination_size_over_max(client: AsyncClient, auth_headers: dict) -> None:
    """Controls allow up to 200."""
    res = await client.get("/api/v1/controls?size=201", headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exceptions_pagination_size_over_max(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get("/api/v1/exceptions?size=200", headers=auth_headers)
    assert res.status_code == 422


# ── LIKE escape ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_findings_search_with_percent(client: AsyncClient, auth_headers: dict) -> None:
    """Search with % should not match everything — wildcard is escaped."""
    res = await client.get("/api/v1/findings?search=%25", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    # With escaped %, search for literal "%" — should find nothing (no titles contain %)
    assert data["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_assets_search_with_underscore(client: AsyncClient, auth_headers: dict) -> None:
    """Search with _ should not match single-char wildcard."""
    res = await client.get("/api/v1/assets?search=_", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["meta"]["total"] == 0


# ── Security headers ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    """All security headers should be present on every response."""
    res = await client.get("/health")
    assert res.status_code == 200

    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin" in res.headers.get("Referrer-Policy", "")
    assert "camera=()" in res.headers.get("Permissions-Policy", "")
    assert "frame-ancestors 'none'" in res.headers.get("Content-Security-Policy", "")
    assert "max-age=" in res.headers.get("Strict-Transport-Security", "")


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient) -> None:
    """X-Request-ID should be present on every response."""
    res = await client.get("/health")
    assert res.headers.get("X-Request-ID") is not None
