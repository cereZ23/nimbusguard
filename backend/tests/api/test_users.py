from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get("/api/v1/users", headers=auth_headers)
    assert res.status_code == 200
    users = res.json()["data"]
    assert len(users) >= 1
    assert users[0]["email"] == "usera@test.com"


@pytest.mark.asyncio
async def test_invite_user(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "newuser@test.com",
            "full_name": "New User",
            "password": "newpassword123",
            "role": "viewer",
        },
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "viewer"


@pytest.mark.asyncio
async def test_invite_duplicate_email(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "dup@test.com",
            "full_name": "Dup",
            "password": "password123",
            "role": "viewer",
        },
    )
    res = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "dup@test.com",
            "full_name": "Dup2",
            "password": "password123",
            "role": "viewer",
        },
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, auth_headers: dict) -> None:
    invite_res = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "rolechange@test.com",
            "full_name": "Role User",
            "password": "password123",
            "role": "viewer",
        },
    )
    user_id = invite_res.json()["data"]["id"]

    res = await client.put(
        f"/api/v1/users/{user_id}/role",
        headers=auth_headers,
        json={"role": "admin"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["role"] == "admin"


@pytest.mark.asyncio
async def test_cannot_change_own_role(client: AsyncClient, auth_headers: dict) -> None:
    # Get current user
    me_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    my_id = me_res.json()["data"]["id"]

    res = await client.put(
        f"/api/v1/users/{my_id}/role",
        headers=auth_headers,
        json={"role": "viewer"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_remove_user(client: AsyncClient, auth_headers: dict) -> None:
    invite_res = await client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "toremove@test.com",
            "full_name": "Remove Me",
            "password": "password123",
            "role": "viewer",
        },
    )
    user_id = invite_res.json()["data"]["id"]

    res = await client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_users_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/users")
    assert res.status_code == 401
