from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INVITE_EMAIL = "invited@example.com"
_ACCEPT_PASSWORD = "Accepted@pass1"
_FULL_NAME = "Invited User"

# Path to the email function as used by the invitations router
_EMAIL_MOCK_PATH = "app.api.invitations.send_invitation_email"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_invitation(
    client: AsyncClient,
    admin_headers: dict,
    *,
    email: str = _INVITE_EMAIL,
    role: str = "viewer",
) -> dict:
    """Create an invitation and return the full response data payload."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock) as _mock_email:
        res = await client.post(
            "/api/v1/invitations",
            headers=admin_headers,
            json={"email": email, "role": role},
        )
    assert res.status_code == 201, res.text
    return res.json()["data"]


# ---------------------------------------------------------------------------
# test_create_invitation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_invitation(client: AsyncClient, auth_headers: dict) -> None:
    """POST /invitations creates an invitation and returns invite_url."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock) as mock_email:
        res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": _INVITE_EMAIL, "role": "viewer"},
        )

    assert res.status_code == 201
    body = res.json()
    assert body["error"] is None

    data = body["data"]
    assert "invite_url" in data
    assert "invitation" in data

    invite = data["invitation"]
    assert invite["email"] == _INVITE_EMAIL
    assert invite["role"] == "viewer"
    assert invite["status"] == "pending"
    assert "id" in invite
    assert "expires_at" in invite

    # The invite_url must contain the raw token as a query parameter
    assert "token=" in data["invite_url"]

    # Email service should have been called exactly once
    mock_email.assert_called_once()
    call_args = mock_email.call_args
    assert call_args.args[0] == _INVITE_EMAIL
    assert "token=" in call_args.args[1]


@pytest.mark.asyncio
async def test_create_invitation_requires_admin(client: AsyncClient) -> None:
    """POST /invitations without auth returns 401."""
    res = await client.post(
        "/api/v1/invitations",
        json={"email": "noauth@example.com", "role": "viewer"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_invitation_invalid_role(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /invitations with an invalid role value returns 422."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "bad-role@example.com", "role": "superuser"},
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_invitation_invalid_email(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /invitations with a malformed email returns 422."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "not-an-email", "role": "viewer"},
        )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# test_list_invitations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_invitations(client: AsyncClient, auth_headers: dict) -> None:
    """GET /invitations returns a list containing created invitations."""
    await _create_invitation(client, auth_headers, email="list-test@example.com")

    res = await client.get("/api/v1/invitations", headers=auth_headers)

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None

    invitations = body["data"]
    assert isinstance(invitations, list)
    emails = {inv["email"] for inv in invitations}
    assert "list-test@example.com" in emails


@pytest.mark.asyncio
async def test_list_invitations_requires_admin(client: AsyncClient) -> None:
    """GET /invitations without auth returns 401."""
    res = await client.get("/api/v1/invitations")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_invitations_viewer_forbidden(
    client: AsyncClient, auth_headers: dict
) -> None:
    """A viewer user cannot list invitations (403)."""
    # Create a viewer user
    create_res = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "viewer-inv@test.com",
            "full_name": "Viewer Inv",
            "password": "Test@pass123",
            "role": "viewer",
        },
    )
    assert create_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer-inv@test.com", "password": "Test@pass123"},
    )
    viewer_token = login_res.cookies.get("access_token")
    assert viewer_token, "access_token cookie missing after login"
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    client.cookies.clear()
    res = await client.get("/api/v1/invitations", headers=viewer_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# test_accept_invitation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_invitation(client: AsyncClient, auth_headers: dict) -> None:
    """POST /invitations/accept with a valid token creates the user account."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        create_res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "accept-me@example.com", "role": "viewer"},
        )
    assert create_res.status_code == 201
    invite_url = create_res.json()["data"]["invite_url"]

    # Extract the raw token from the invite URL
    raw_token = invite_url.split("token=", 1)[1]

    res = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "password": _ACCEPT_PASSWORD,
            "full_name": _FULL_NAME,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert "message" in body["data"]

    # Verify the new user can log in
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "accept-me@example.com", "password": _ACCEPT_PASSWORD},
    )
    assert login_res.status_code == 200
    assert login_res.cookies.get("access_token")


@pytest.mark.asyncio
async def test_accept_invitation_no_auth_required(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /invitations/accept does not require authentication."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        create_res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "noauth-accept@example.com", "role": "viewer"},
        )
    raw_token = create_res.json()["data"]["invite_url"].split("token=", 1)[1]

    # Explicitly send no auth headers
    res = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "password": _ACCEPT_PASSWORD,
            "full_name": _FULL_NAME,
        },
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# test_accept_invitation_invalid_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_invitation_invalid_token(client: AsyncClient) -> None:
    """POST /invitations/accept with a bogus token returns 400."""
    res = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": "this-is-not-a-real-token-at-all",
            "password": _ACCEPT_PASSWORD,
            "full_name": _FULL_NAME,
        },
    )
    assert res.status_code == 400
    assert "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_accept_invitation_weak_password(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /invitations/accept with a password violating SEC-04 policy returns 422."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        create_res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "weak-pw@example.com", "role": "viewer"},
        )
    raw_token = create_res.json()["data"]["invite_url"].split("token=", 1)[1]

    res = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "password": "weakpass",  # no uppercase, no digit, no special char
            "full_name": _FULL_NAME,
        },
    )
    # SEC-04 raises ValueError("Password …") → 422 via the endpoint mapping
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_accept_invitation_already_accepted(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Using the same invitation token twice returns 400 on the second attempt."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        create_res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "double-accept@example.com", "role": "viewer"},
        )
    raw_token = create_res.json()["data"]["invite_url"].split("token=", 1)[1]

    accept_payload = {
        "token": raw_token,
        "password": _ACCEPT_PASSWORD,
        "full_name": _FULL_NAME,
    }

    first = await client.post("/api/v1/invitations/accept", json=accept_payload)
    assert first.status_code == 200

    second = await client.post("/api/v1/invitations/accept", json=accept_payload)
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# test_revoke_invitation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_invitation(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /invitations/{id} revokes a pending invitation (204)."""
    payload = await _create_invitation(client, auth_headers, email="revoke-me@example.com")
    invitation_id = payload["invitation"]["id"]

    res = await client.delete(
        f"/api/v1/invitations/{invitation_id}",
        headers=auth_headers,
    )
    assert res.status_code == 204

    # After revocation the token must no longer be usable
    invite_url = payload["invite_url"]
    raw_token = invite_url.split("token=", 1)[1]

    accept_res = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "password": _ACCEPT_PASSWORD,
            "full_name": _FULL_NAME,
        },
    )
    assert accept_res.status_code == 400
    assert "revoked" in accept_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_revoke_invitation_not_found(
    client: AsyncClient, auth_headers: dict
) -> None:
    """DELETE /invitations/{id} for a non-existent ID returns 400."""
    res = await client.delete(
        f"/api/v1/invitations/{uuid.uuid4()}",
        headers=auth_headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_revoke_invitation_requires_admin(client: AsyncClient) -> None:
    """DELETE /invitations/{id} without auth returns 401."""
    res = await client.delete(f"/api/v1/invitations/{uuid.uuid4()}")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# test_invitation_requires_admin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invitation_requires_admin(
    client: AsyncClient, auth_headers: dict
) -> None:
    """A viewer user cannot create invitations (403)."""
    # Create a viewer inside tenant A
    viewer_create = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "viewer-inv2@test.com",
            "full_name": "Viewer Inv2",
            "password": "Test@pass123",
            "role": "viewer",
        },
    )
    assert viewer_create.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer-inv2@test.com", "password": "Test@pass123"},
    )
    viewer_token = login_res.cookies.get("access_token")
    assert viewer_token, "access_token cookie missing after login"
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    client.cookies.clear()
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/invitations",
            headers=viewer_headers,
            json={"email": "nope@example.com", "role": "viewer"},
        )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# test_invitation_tenant_isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invitation_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
) -> None:
    """Tenant B cannot list tenant A's invitations."""
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()
    await _create_invitation(
        client, auth_headers, email="tenant-a-invite@example.com"
    )

    # Clear cookies again before tenant B request
    client.cookies.clear()
    res_b = await client.get("/api/v1/invitations", headers=second_auth_headers)
    assert res_b.status_code == 200

    emails_b = {inv["email"] for inv in res_b.json()["data"]}
    assert "tenant-a-invite@example.com" not in emails_b


@pytest.mark.asyncio
async def test_invitation_tenant_b_cannot_revoke_tenant_a_invite(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
) -> None:
    """Tenant B cannot revoke an invitation that belongs to tenant A."""
    # Clear cookies to prevent cookie-based auth bleed
    client.cookies.clear()
    payload = await _create_invitation(
        client, auth_headers, email="cross-tenant-revoke@example.com"
    )
    invitation_id = payload["invitation"]["id"]

    # Clear cookies again before tenant B request
    client.cookies.clear()
    res = await client.delete(
        f"/api/v1/invitations/{invitation_id}",
        headers=second_auth_headers,
    )
    # The invitation is not found in tenant B's scope
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# test_create_duplicate_invitation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_duplicate_invitation(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /invitations for the same email twice (while pending) returns 409."""
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        first = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "dup-invite@example.com", "role": "viewer"},
        )
    assert first.status_code == 201

    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        second = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "dup-invite@example.com", "role": "admin"},
        )
    assert second.status_code == 409
    assert "pending" in second.json()["detail"].lower() or "exists" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_invitation_for_existing_user(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /invitations for a user email that already has an account returns 409."""
    # usera@test.com is the registered admin user (created by auth_headers fixture)
    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/invitations",
            headers=auth_headers,
            json={"email": "usera@test.com", "role": "viewer"},
        )
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# test_resend_invitation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resend_invitation(client: AsyncClient, auth_headers: dict) -> None:
    """POST /invitations/resend generates a new token and returns a new invite_url."""
    payload = await _create_invitation(
        client, auth_headers, email="resend-me@example.com"
    )
    invitation_id = payload["invitation"]["id"]
    original_url = payload["invite_url"]

    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock) as mock_email:
        res = await client.post(
            "/api/v1/invitations/resend",
            headers=auth_headers,
            json={"invitation_id": invitation_id},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    new_url = body["data"]["invite_url"]
    # The new URL must contain a different token
    assert new_url != original_url
    assert "token=" in new_url

    # Email re-sent to same address
    mock_email.assert_called_once()
    assert mock_email.call_args.args[0] == "resend-me@example.com"


@pytest.mark.asyncio
async def test_resend_invitation_old_token_invalid(
    client: AsyncClient, auth_headers: dict
) -> None:
    """After resending, the original token must no longer be valid."""
    payload = await _create_invitation(
        client, auth_headers, email="resend-old-token@example.com"
    )
    invitation_id = payload["invitation"]["id"]
    old_token = payload["invite_url"].split("token=", 1)[1]

    with patch(_EMAIL_MOCK_PATH, new_callable=AsyncMock):
        await client.post(
            "/api/v1/invitations/resend",
            headers=auth_headers,
            json={"invitation_id": invitation_id},
        )

    accept_res = await client.post(
        "/api/v1/invitations/accept",
        json={
            "token": old_token,
            "password": _ACCEPT_PASSWORD,
            "full_name": _FULL_NAME,
        },
    )
    assert accept_res.status_code == 400
