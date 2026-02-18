"""Tests for SSO admin endpoints at /api/v1/sso."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# ── Shared test data ──────────────────────────────────────────────────

_VALID_SSO_PAYLOAD = {
    "provider": "azure_ad",
    "client_id": "11111111-2222-3333-4444-555555555555",
    "client_secret": "super-secret-value",
    "issuer_url": "https://login.microsoftonline.com/fake-tenant-id/v2.0",
    "metadata_url": None,
    "domain_restriction": None,
    "auto_provision": True,
    "default_role": "viewer",
}

_SSO_CONFIG_URL = "/api/v1/sso/config"
_SSO_TEST_URL = "/api/v1/sso/test"


# ── 1. GET with no existing config ────────────────────────────────────


async def test_get_sso_config_no_config(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /sso/config returns null data when no config exists for the tenant."""
    res = await client.get(_SSO_CONFIG_URL, headers=auth_headers)

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert body["data"] is None


# ── 2. PUT creates a config ───────────────────────────────────────────


async def test_create_sso_config(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT /sso/config creates a new SSO config and returns expected fields."""
    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    data = body["data"]

    assert data["provider"] == "azure_ad"
    assert data["client_id"] == _VALID_SSO_PAYLOAD["client_id"]
    assert data["issuer_url"] == _VALID_SSO_PAYLOAD["issuer_url"]
    assert data["auto_provision"] is True
    assert data["default_role"] == "viewer"
    assert data["is_active"] is False  # new config starts inactive
    assert "id" in data
    # client_secret must NOT appear in the response
    assert "client_secret" not in data
    assert "client_secret_encrypted" not in data


# ── 3. GET returns config after PUT ──────────────────────────────────


async def test_get_sso_config_after_create(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /sso/config returns the config previously created with PUT."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    res = await client.get(_SSO_CONFIG_URL, headers=auth_headers)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data is not None
    assert data["provider"] == "azure_ad"
    assert data["issuer_url"] == _VALID_SSO_PAYLOAD["issuer_url"]
    assert data["client_id"] == _VALID_SSO_PAYLOAD["client_id"]


# ── 4. PATCH enables the config ──────────────────────────────────────


async def test_patch_sso_config_enable(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PATCH /sso/config with is_active=true activates the config."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    res = await client.patch(
        _SSO_CONFIG_URL, headers=auth_headers, json={"is_active": True}
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_active"] is True
    # Other fields should remain unchanged
    assert data["provider"] == "azure_ad"
    assert data["auto_provision"] is True


# ── 5. DELETE removes config ──────────────────────────────────────────


async def test_delete_sso_config(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """DELETE /sso/config removes the config; subsequent GET returns null data."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    res = await client.delete(_SSO_CONFIG_URL, headers=auth_headers)

    assert res.status_code == 200
    assert res.json()["data"] is None

    # Verify the config is gone
    get_res = await client.get(_SSO_CONFIG_URL, headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"] is None


# ── 6. Auth required ──────────────────────────────────────────────────


async def test_sso_config_requires_auth(client: AsyncClient) -> None:
    """All SSO admin endpoints return 401 when no Authorization header is provided."""
    endpoints = [
        ("GET", _SSO_CONFIG_URL),
        ("PUT", _SSO_CONFIG_URL),
        ("PATCH", _SSO_CONFIG_URL),
        ("DELETE", _SSO_CONFIG_URL),
        ("POST", _SSO_TEST_URL),
    ]
    for method, url in endpoints:
        res = await client.request(method, url, json=_VALID_SSO_PAYLOAD)
        assert res.status_code == 401, (
            f"Expected 401 for {method} {url}, got {res.status_code}"
        )


# ── 7. Tenant isolation ───────────────────────────────────────────────


async def test_sso_config_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    second_auth_headers: dict[str, str],
) -> None:
    """Tenant B cannot see Tenant A's SSO config; their GET returns null data."""
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    # Tenant A creates a config
    put_res = await client.put(
        _SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD
    )
    assert put_res.status_code == 200

    # Clear cookies again before tenant B request
    client.cookies.clear()

    # Tenant B should see no config
    res = await client.get(_SSO_CONFIG_URL, headers=second_auth_headers)
    assert res.status_code == 200
    assert res.json()["data"] is None


# ── 8. SSRF blocked — private IP ─────────────────────────────────────


async def test_sso_config_ssrf_blocked(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT with issuer_url pointing to AWS metadata endpoint returns 422."""
    payload = {**_VALID_SSO_PAYLOAD, "issuer_url": "http://169.254.169.254/latest/meta-data"}

    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=payload)

    assert res.status_code == 422


# ── 9. HTTP (non-HTTPS) blocked ───────────────────────────────────────


async def test_sso_config_http_blocked(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT with issuer_url using http:// (non-HTTPS) returns 422."""
    payload = {**_VALID_SSO_PAYLOAD, "issuer_url": "http://example.com/oauth/v2"}

    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=payload)

    assert res.status_code == 422


# ── 10. PATCH without existing config returns 404 ────────────────────


async def test_patch_not_found(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PATCH /sso/config returns 404 when no config has been created yet."""
    res = await client.patch(
        _SSO_CONFIG_URL, headers=auth_headers, json={"is_active": True}
    )

    assert res.status_code == 404


# ── Additional: PUT is idempotent (update existing config) ────────────


async def test_put_sso_config_overwrites_existing(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Second PUT with different fields replaces the existing config."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    updated_payload = {
        **_VALID_SSO_PAYLOAD,
        "provider": "okta",
        "client_id": "new-client-id",
        "issuer_url": "https://dev-123456.okta.com",
    }
    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=updated_payload)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["provider"] == "okta"
    assert data["client_id"] == "new-client-id"
    assert data["issuer_url"] == "https://dev-123456.okta.com"

    # GET should reflect the update — no duplicate rows
    get_res = await client.get(_SSO_CONFIG_URL, headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["provider"] == "okta"


# ── Additional: DELETE on non-existent config returns 404 ────────────


async def test_delete_sso_config_not_found(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """DELETE /sso/config returns 404 when no config exists."""
    res = await client.delete(_SSO_CONFIG_URL, headers=auth_headers)

    assert res.status_code == 404


# ── Additional: POST /sso/test with no config returns 404 ────────────


async def test_sso_test_no_config(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /sso/test returns 404 when no SSO config has been configured."""
    res = await client.post(_SSO_TEST_URL, headers=auth_headers)

    assert res.status_code == 404


# ── Additional: POST /sso/test with unreachable IdP returns failure ──


async def test_sso_test_discovery_failure(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /sso/test returns success=false when OIDC discovery fails."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    with patch(
        "app.api.sso.discover_oidc_config",
        new=AsyncMock(side_effect=ValueError("connection refused")),
    ):
        res = await client.post(_SSO_TEST_URL, headers=auth_headers)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is False
    assert "connection refused" in data["error"]


# ── Additional: POST /sso/test with reachable IdP returns success ─────


async def test_sso_test_discovery_success(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /sso/test returns success=true when OIDC discovery succeeds."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    fake_oidc_doc = {
        "issuer": "https://login.microsoftonline.com/fake-tenant-id/v2.0",
        "authorization_endpoint": "https://login.microsoftonline.com/fake-tenant-id/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoftonline.com/fake-tenant-id/oauth2/v2.0/token",
    }

    with patch(
        "app.api.sso.discover_oidc_config",
        new=AsyncMock(return_value=fake_oidc_doc),
    ):
        res = await client.post(_SSO_TEST_URL, headers=auth_headers)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is True
    assert data["issuer"] == fake_oidc_doc["issuer"]
    assert data["authorization_endpoint"] == fake_oidc_doc["authorization_endpoint"]
    assert data["token_endpoint"] == fake_oidc_doc["token_endpoint"]
    assert data["error"] is None


# ── Additional: validation — invalid provider value ───────────────────


async def test_put_sso_config_invalid_provider(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT rejects an unrecognised provider value with 422."""
    payload = {**_VALID_SSO_PAYLOAD, "provider": "not_a_real_provider"}

    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=payload)

    assert res.status_code == 422


# ── Additional: validation — invalid default_role value ──────────────


async def test_put_sso_config_invalid_default_role(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT rejects an unrecognised default_role value with 422."""
    payload = {**_VALID_SSO_PAYLOAD, "default_role": "superuser"}

    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=payload)

    assert res.status_code == 422


# ── Additional: metadata_url must also use https:// ──────────────────


async def test_put_sso_config_metadata_url_http_blocked(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT rejects metadata_url using http:// with 422."""
    payload = {
        **_VALID_SSO_PAYLOAD,
        "metadata_url": "http://my-idp.internal/.well-known/openid-configuration",
    }

    res = await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=payload)

    assert res.status_code == 422


# ── Additional: PATCH partial update preserves unset fields ──────────


async def test_patch_sso_config_partial_update(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PATCH with only auto_provision=false leaves all other fields unchanged."""
    await client.put(_SSO_CONFIG_URL, headers=auth_headers, json=_VALID_SSO_PAYLOAD)

    res = await client.patch(
        _SSO_CONFIG_URL, headers=auth_headers, json={"auto_provision": False}
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["auto_provision"] is False
    # Other fields must be unchanged
    assert data["provider"] == "azure_ad"
    assert data["default_role"] == "viewer"
    assert data["issuer_url"] == _VALID_SSO_PAYLOAD["issuer_url"]
