"""Auth endpoint tests — adapted for invitation-only registration model."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_test_user(email: str = "test@example.com", password: str = "Secure@pass123") -> str:
    """Create a user + tenant directly in DB and return access token."""
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.services.auth import create_access_token, hash_password
    from tests.conftest import TestSession

    async with TestSession() as db:
        tenant = Tenant(name=f"Tenant {email}", slug=email.replace("@", "-").replace(".", "-"))
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password(password),
            full_name="Test User",
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await db.refresh(tenant)
        return create_access_token(str(user.id), str(tenant.id))


@pytest.mark.asyncio
async def test_register_requires_auth(client: AsyncClient) -> None:
    """Registration requires authentication (invitation-only model)."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "Secure@pass123",
            "full_name": "Test User",
            "tenant_name": "Test Tenant",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """Authenticated admin can create a new tenant."""
    response = await client.post(
        "/api/v1/auth/register",
        headers=auth_headers,
        json={
            "email": "newtenant@example.com",
            "password": "Secure@pass123",
            "full_name": "New Tenant Admin",
            "tenant_name": "New Tenant",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["email"] == "newtenant@example.com"
    assert data["data"]["tenant_name"] == "New Tenant"


@pytest.mark.asyncio
async def test_login(client: AsyncClient) -> None:
    await _create_test_user("login@example.com", "Secure@pass123")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "Secure@pass123"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["token_type"] == "bearer"
    assert response.cookies.get("access_token")
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await _create_test_user("wrong@example.com", "Secure@pass123")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient) -> None:
    await _create_test_user("refresh@example.com", "Secure@pass123")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "Secure@pass123"},
    )
    refresh_token = login.cookies.get("refresh_token")
    assert refresh_token

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert response.cookies.get("access_token")


@pytest.mark.asyncio
async def test_me_with_cookie(client: AsyncClient) -> None:
    token = await _create_test_user("metest@example.com")
    response = await client.get(
        "/api/v1/auth/me",
        cookies={"access_token": token},
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "metest@example.com"


@pytest.mark.asyncio
async def test_me_with_bearer_header(client: AsyncClient) -> None:
    token = await _create_test_user("bearer@example.com")
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "bearer@example.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    await _create_test_user("logout@example.com", "Secure@pass123")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "Secure@pass123"},
    )
    access_token = login.cookies.get("access_token")
    refresh_token = login.cookies.get("refresh_token")
    assert access_token
    assert refresh_token

    response = await client.post(
        "/api/v1/auth/logout",
        cookies={"access_token": access_token, "refresh_token": refresh_token},
    )
    assert response.status_code == 200

    # Refresh token should be revoked after logout
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401
