from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_get_branding_default(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """GET /branding returns default branding for a new tenant."""
    res = await client.get("/api/v1/branding", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["primary_color"] == "#6366f1"
    assert data["logo_url"] is None
    assert data["favicon_url"] is None
    # company_name should default to the tenant name (set during registration)
    assert data["company_name"]


async def test_get_branding_unauthenticated(client: AsyncClient) -> None:
    """GET /branding requires authentication."""
    res = await client.get("/api/v1/branding")
    assert res.status_code == 401


async def test_update_branding_company_name(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """PUT /branding updates company_name."""
    res = await client.put(
        "/api/v1/branding",
        headers=auth_headers,
        json={"company_name": "Acme Corp"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["company_name"] == "Acme Corp"
    assert data["primary_color"] == "#6366f1"  # unchanged


async def test_update_branding_primary_color(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """PUT /branding updates primary_color."""
    res = await client.put(
        "/api/v1/branding",
        headers=auth_headers,
        json={"primary_color": "#ff5500"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["primary_color"] == "#ff5500"


async def test_update_branding_invalid_color(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """PUT /branding rejects invalid hex color."""
    res = await client.put(
        "/api/v1/branding",
        headers=auth_headers,
        json={"primary_color": "not-a-color"},
    )
    assert res.status_code == 422


async def test_update_branding_both_fields(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """PUT /branding can update both fields at once."""
    res = await client.put(
        "/api/v1/branding",
        headers=auth_headers,
        json={"company_name": "NewCo", "primary_color": "#123456"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["company_name"] == "NewCo"
    assert data["primary_color"] == "#123456"


async def test_update_branding_persists(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """Branding changes persist across GET requests."""
    await client.put(
        "/api/v1/branding",
        headers=auth_headers,
        json={"company_name": "PersistCo", "primary_color": "#abcdef"},
    )
    res = await client.get("/api/v1/branding", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["company_name"] == "PersistCo"
    assert data["primary_color"] == "#abcdef"


async def test_upload_logo_png(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """POST /branding/logo accepts a PNG file and returns updated branding."""
    # Create a minimal 1x1 PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    res = await client.post(
        "/api/v1/branding/logo",
        headers=auth_headers,
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["logo_url"] is not None
    assert "logo.png" in data["logo_url"]


async def test_upload_logo_too_large(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """POST /branding/logo rejects files over 500 KB."""
    large_bytes = b"\x00" * (500 * 1024 + 1)
    res = await client.post(
        "/api/v1/branding/logo",
        headers=auth_headers,
        files={"file": ("big.png", io.BytesIO(large_bytes), "image/png")},
    )
    assert res.status_code == 400
    assert "too large" in res.json()["detail"].lower()


async def test_upload_logo_invalid_type(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """POST /branding/logo rejects non-image files."""
    res = await client.post(
        "/api/v1/branding/logo",
        headers=auth_headers,
        files={"file": ("doc.pdf", io.BytesIO(b"fake"), "application/pdf")},
    )
    assert res.status_code == 400
    assert "invalid file type" in res.json()["detail"].lower()


async def test_serve_logo_not_found(client: AsyncClient) -> None:
    """GET /branding/logo/{tenant_id}/{filename} returns 404 for missing logos."""
    res = await client.get("/api/v1/branding/logo/nonexistent/logo.png")
    assert res.status_code == 404


async def test_branding_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    second_auth_headers: dict[str, str],
) -> None:
    """Branding changes for one tenant do not affect another."""
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    # Update tenant A
    await client.put(
        "/api/v1/branding",
        headers=auth_headers,
        json={"company_name": "Tenant A Corp"},
    )

    # Clear cookies again before tenant B request
    client.cookies.clear()

    # Read tenant B -- should still have default
    res = await client.get("/api/v1/branding", headers=second_auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["company_name"] != "Tenant A Corp"
