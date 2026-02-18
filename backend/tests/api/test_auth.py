from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "Secure@pass123",
            "full_name": "Test User",
            "tenant_name": "Test Tenant",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["token_type"] == "bearer"
    assert data["error"] is None

    # Tokens should be in httpOnly cookies, not in the response body
    assert "access_token" not in data["data"]
    assert "refresh_token" not in data["data"]
    assert response.cookies.get("access_token")
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "Secure@pass123",
        "full_name": "Test User",
        "tenant_name": "Test Tenant",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "Secure@pass123",
            "full_name": "Login User",
            "tenant_name": "Login Tenant",
        },
    )
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
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "Secure@pass123",
            "full_name": "Wrong User",
            "tenant_name": "Wrong Tenant",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "Secure@pass123",
            "full_name": "Refresh User",
            "tenant_name": "Refresh Tenant",
        },
    )
    refresh_token = reg.cookies.get("refresh_token")
    assert refresh_token

    # Send refresh token via JSON body (backward compat)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert response.json()["data"]["token_type"] == "bearer"
    assert response.cookies.get("access_token")
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_me_with_cookie(client: AsyncClient) -> None:
    """Test that /auth/me works when access_token is sent via cookie."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "metest@example.com",
            "password": "Secure@pass123",
            "full_name": "Me User",
            "tenant_name": "Me Tenant",
        },
    )
    access_token = reg.cookies.get("access_token")
    assert access_token

    response = await client.get(
        "/api/v1/auth/me",
        cookies={"access_token": access_token},
    )
    assert response.status_code == 200
    user = response.json()["data"]
    assert user["email"] == "metest@example.com"


@pytest.mark.asyncio
async def test_me_with_bearer_header(client: AsyncClient) -> None:
    """Test backward compat: /auth/me still works with Authorization header."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bearer@example.com",
            "password": "Secure@pass123",
            "full_name": "Bearer User",
            "tenant_name": "Bearer Tenant",
        },
    )
    access_token = reg.cookies.get("access_token")
    assert access_token

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "bearer@example.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout@example.com",
            "password": "Secure@pass123",
            "full_name": "Logout User",
            "tenant_name": "Logout Tenant",
        },
    )
    access_token = reg.cookies.get("access_token")
    refresh_token = reg.cookies.get("refresh_token")
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
