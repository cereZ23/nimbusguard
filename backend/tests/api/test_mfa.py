from __future__ import annotations

import pyotp
import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGISTER_URL = "/api/v1/auth/register"
_LOGIN_URL = "/api/v1/auth/login"
_MFA_SETUP_URL = "/api/v1/auth/mfa/setup"
_MFA_VERIFY_URL = "/api/v1/auth/mfa/verify"
_MFA_DISABLE_URL = "/api/v1/auth/mfa/disable"
_MFA_LOGIN_URL = "/api/v1/auth/mfa/login"

_PASSWORD = "Test@pass123"


async def _register_and_get_token(client: AsyncClient, email: str) -> str:
    """Register a fresh user and return the access_token."""
    res = await client.post(
        _REGISTER_URL,
        json={
            "email": email,
            "password": _PASSWORD,
            "full_name": "MFA Test User",
            "tenant_name": f"Tenant {email}",
        },
    )
    assert res.status_code == 201, res.text
    token = res.cookies.get("access_token")
    assert token, "access_token cookie missing after registration"
    return token


async def _enable_mfa(client: AsyncClient, token: str) -> tuple[str, list[str]]:
    """Run the full setup→verify flow and return (secret, backup_codes)."""
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Setup — get secret
    setup_res = await client.post(_MFA_SETUP_URL, headers=headers)
    assert setup_res.status_code == 200, setup_res.text
    secret = setup_res.json()["data"]["secret"]

    # 2. Verify — activate with a fresh TOTP code
    code = pyotp.TOTP(secret).now()
    verify_res = await client.post(
        _MFA_VERIFY_URL,
        headers=headers,
        json={"code": code},
    )
    assert verify_res.status_code == 200, verify_res.text
    backup_codes: list[str] = verify_res.json()["data"]["backup_codes"]
    return secret, backup_codes


# ---------------------------------------------------------------------------
# 1. mfa/setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mfa_setup_success(client: AsyncClient) -> None:
    """POST /mfa/setup returns secret and otpauth provisioning URI."""
    token = await _register_and_get_token(client, "setup_ok@example.com")

    res = await client.post(
        _MFA_SETUP_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    data = body["data"]
    assert "secret" in data
    assert len(data["secret"]) > 0
    assert "provisioning_uri" in data
    assert data["provisioning_uri"].startswith("otpauth://totp/")
    # Provisioning URI must include the user email and the issuer
    assert "CSPM" in data["provisioning_uri"]
    assert "setup_ok%40example.com" in data["provisioning_uri"] or "setup_ok@example.com" in data["provisioning_uri"]


@pytest.mark.asyncio
async def test_mfa_setup_already_enabled(client: AsyncClient) -> None:
    """POST /mfa/setup on an account with MFA already enabled returns 400."""
    token = await _register_and_get_token(client, "setup_dup@example.com")
    await _enable_mfa(client, token)

    res = await client.post(
        _MFA_SETUP_URL,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 400
    assert "already enabled" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. mfa/verify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mfa_verify_success(client: AsyncClient) -> None:
    """POST /mfa/verify with a valid TOTP code activates MFA and returns 8 backup codes."""
    token = await _register_and_get_token(client, "verify_ok@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Initiate setup
    setup_res = await client.post(_MFA_SETUP_URL, headers=headers)
    assert setup_res.status_code == 200
    secret = setup_res.json()["data"]["secret"]

    code = pyotp.TOTP(secret).now()
    verify_res = await client.post(
        _MFA_VERIFY_URL,
        headers=headers,
        json={"code": code},
    )

    assert verify_res.status_code == 200
    body = verify_res.json()
    assert body["error"] is None
    backup_codes = body["data"]["backup_codes"]
    assert isinstance(backup_codes, list)
    assert len(backup_codes) == 8
    # Each backup code should be 8 uppercase hex characters
    for bc in backup_codes:
        assert len(bc) == 8
        assert bc == bc.upper()

    # Confirm MFA is now enabled by checking /auth/me
    me_res = await client.get(
        "/api/v1/auth/me",
        headers=headers,
    )
    assert me_res.status_code == 200
    assert me_res.json()["data"]["mfa_enabled"] is True


@pytest.mark.asyncio
async def test_mfa_verify_invalid_code(client: AsyncClient) -> None:
    """POST /mfa/verify with a wrong code returns 400."""
    token = await _register_and_get_token(client, "verify_bad@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    setup_res = await client.post(_MFA_SETUP_URL, headers=headers)
    assert setup_res.status_code == 200

    res = await client.post(
        _MFA_VERIFY_URL,
        headers=headers,
        json={"code": "000000"},
    )

    assert res.status_code == 400
    assert "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mfa_verify_no_setup(client: AsyncClient) -> None:
    """POST /mfa/verify without calling setup first returns 400."""
    token = await _register_and_get_token(client, "verify_nosetup@example.com")

    res = await client.post(
        _MFA_VERIFY_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "123456"},
    )

    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "setup" in detail or "not been initiated" in detail


@pytest.mark.asyncio
async def test_mfa_verify_already_enabled(client: AsyncClient) -> None:
    """POST /mfa/verify when MFA is already fully enabled returns 400."""
    token = await _register_and_get_token(client, "verify_already@example.com")
    secret, _ = await _enable_mfa(client, token)

    # Attempt to call verify again with a fresh valid code
    code = pyotp.TOTP(secret).now()
    res = await client.post(
        _MFA_VERIFY_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"code": code},
    )

    assert res.status_code == 400
    assert "already enabled" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. mfa/disable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mfa_disable_success(client: AsyncClient) -> None:
    """POST /mfa/disable with the correct password disables MFA."""
    token = await _register_and_get_token(client, "disable_ok@example.com")
    await _enable_mfa(client, token)
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.post(
        _MFA_DISABLE_URL,
        headers=headers,
        json={"password": _PASSWORD},
    )

    assert res.status_code == 200
    assert res.json()["error"] is None

    # Confirm MFA is now off
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.json()["data"]["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_mfa_disable_wrong_password(client: AsyncClient) -> None:
    """POST /mfa/disable with an incorrect password returns 401."""
    token = await _register_and_get_token(client, "disable_bad@example.com")
    await _enable_mfa(client, token)

    res = await client.post(
        _MFA_DISABLE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "WrongPass@999"},
    )

    assert res.status_code == 401
    assert "invalid password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mfa_disable_not_enabled(client: AsyncClient) -> None:
    """POST /mfa/disable when MFA is not active returns 400."""
    token = await _register_and_get_token(client, "disable_off@example.com")

    res = await client.post(
        _MFA_DISABLE_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"password": _PASSWORD},
    )

    assert res.status_code == 400
    assert "not enabled" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. mfa/login — TOTP code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mfa_login_success(client: AsyncClient) -> None:
    """Full flow: register → enable MFA → login → mfa/login with TOTP code."""
    email = "login_totp@example.com"
    token = await _register_and_get_token(client, email)
    secret, _ = await _enable_mfa(client, token)

    # Password-only login must now return mfa_required + mfa_token (no cookies)
    login_res = await client.post(
        _LOGIN_URL,
        json={"email": email, "password": _PASSWORD},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()["data"]
    assert login_data["mfa_required"] is True
    mfa_token = login_data["mfa_token"]
    assert mfa_token
    # No full-auth cookies should be issued at this stage
    assert not login_res.cookies.get("access_token")
    assert not login_res.cookies.get("refresh_token")

    # Complete login with TOTP
    code = pyotp.TOTP(secret).now()
    mfa_res = await client.post(
        _MFA_LOGIN_URL,
        json={"mfa_token": mfa_token, "code": code},
    )

    assert mfa_res.status_code == 200
    assert mfa_res.json()["data"]["token_type"] == "bearer"
    assert mfa_res.json()["error"] is None
    # Full-auth cookies must be present after successful MFA login
    assert mfa_res.cookies.get("access_token")
    assert mfa_res.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_mfa_login_backup_code(client: AsyncClient) -> None:
    """POST /mfa/login with a valid backup code issues full auth and consumes the code."""
    email = "login_backup@example.com"
    token = await _register_and_get_token(client, email)
    _secret, backup_codes = await _enable_mfa(client, token)

    login_res = await client.post(
        _LOGIN_URL,
        json={"email": email, "password": _PASSWORD},
    )
    mfa_token = login_res.json()["data"]["mfa_token"]

    # Use the first backup code
    backup_code = backup_codes[0]
    mfa_res = await client.post(
        _MFA_LOGIN_URL,
        json={"mfa_token": mfa_token, "code": backup_code},
    )

    assert mfa_res.status_code == 200
    assert mfa_res.cookies.get("access_token")

    # The same backup code must not work a second time
    login_res2 = await client.post(
        _LOGIN_URL,
        json={"email": email, "password": _PASSWORD},
    )
    mfa_token2 = login_res2.json()["data"]["mfa_token"]

    mfa_res2 = await client.post(
        _MFA_LOGIN_URL,
        json={"mfa_token": mfa_token2, "code": backup_code},
    )
    assert mfa_res2.status_code == 401


@pytest.mark.asyncio
async def test_mfa_login_invalid_code(client: AsyncClient) -> None:
    """POST /mfa/login with a wrong TOTP code returns 401."""
    email = "login_invalid@example.com"
    token = await _register_and_get_token(client, email)
    await _enable_mfa(client, token)

    login_res = await client.post(
        _LOGIN_URL,
        json={"email": email, "password": _PASSWORD},
    )
    mfa_token = login_res.json()["data"]["mfa_token"]

    res = await client.post(
        _MFA_LOGIN_URL,
        json={"mfa_token": mfa_token, "code": "000000"},
    )

    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mfa_login_expired_token(client: AsyncClient) -> None:
    """POST /mfa/login with a syntactically invalid / fabricated mfa_token returns 401."""
    res = await client.post(
        _MFA_LOGIN_URL,
        json={"mfa_token": "not.a.valid.jwt.token", "code": "123456"},
    )

    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower() or "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mfa_login_with_access_token_rejected(client: AsyncClient) -> None:
    """POST /mfa/login with a regular access_token (not mfa_pending) must be rejected."""
    email = "login_wrongtype@example.com"
    access_token = await _register_and_get_token(client, email)
    await _enable_mfa(client, token=access_token)

    login_res = await client.post(
        _LOGIN_URL,
        json={"email": email, "password": _PASSWORD},
    )
    _secret_unused = login_res.json()["data"]
    # Use the access_token (wrong type) instead of the mfa_token
    res = await client.post(
        _MFA_LOGIN_URL,
        json={"mfa_token": access_token, "code": "123456"},
    )

    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 5. Auth-required guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mfa_setup_requires_auth(client: AsyncClient) -> None:
    """POST /mfa/setup without Authorization header returns 401."""
    res = await client.post(_MFA_SETUP_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_requires_auth(client: AsyncClient) -> None:
    """POST /mfa/verify without Authorization header returns 401."""
    res = await client.post(_MFA_VERIFY_URL, json={"code": "123456"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_mfa_disable_requires_auth(client: AsyncClient) -> None:
    """POST /mfa/disable without Authorization header returns 401."""
    res = await client.post(_MFA_DISABLE_URL, json={"password": _PASSWORD})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_mfa_requires_auth_all_endpoints(client: AsyncClient) -> None:
    """All three protected MFA endpoints reject requests with an invalid Bearer token."""
    bad_headers = {"Authorization": "Bearer invalid.token.here"}

    for url, payload in [
        (_MFA_SETUP_URL, {}),
        (_MFA_VERIFY_URL, {"code": "123456"}),
        (_MFA_DISABLE_URL, {"password": _PASSWORD}),
    ]:
        res = await client.post(url, headers=bad_headers, json=payload)
        assert res.status_code == 401, f"Expected 401 for {url}, got {res.status_code}"
