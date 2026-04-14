from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_audit_log_created_on_login(client: AsyncClient) -> None:
    """Login should create an audit log entry."""
    # Create user directly in DB (register requires auth)
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.services.auth import hash_password
    from tests.conftest import TestSession

    async with TestSession() as db:
        tenant = Tenant(name="Audit Tenant", slug="audit-tenant")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email="audit@test.com",
            hashed_password=hash_password("Tr0ub4dor&3"),
            full_name="Audit User",
            role="admin",
        )
        db.add(user)
        await db.commit()

    # Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "audit@test.com", "password": "Tr0ub4dor&3"},
    )
    assert login_res.status_code == 200
    token = login_res.cookies.get("access_token")
    assert token, "access_token cookie not set in login response"
    headers = {"Authorization": f"Bearer {token}"}

    # Check audit logs
    res = await client.get("/api/v1/audit-logs", headers=headers)
    assert res.status_code == 200
    logs = res.json()["data"]
    assert any(log["action"] == "user.login" for log in logs)


@pytest.mark.asyncio
async def test_audit_log_on_account_create(client: AsyncClient, auth_headers: dict) -> None:
    """Creating an account should create an audit log entry."""
    await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Audit Test Account",
            "provider_account_id": "sub-audit-test",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )

    res = await client.get("/api/v1/audit-logs", headers=auth_headers)
    assert res.status_code == 200
    logs = res.json()["data"]
    assert any(log["action"] == "account.create" for log in logs)


@pytest.mark.asyncio
async def test_audit_log_filter_by_action(client: AsyncClient, auth_headers: dict) -> None:
    """Should filter audit logs by action."""
    # Create an account (generates audit log)
    await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Filter Test",
            "provider_account_id": "sub-filter-test",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )

    # Filter by action
    res = await client.get(
        "/api/v1/audit-logs",
        headers=auth_headers,
        params={"action": "account.create"},
    )
    assert res.status_code == 200
    logs = res.json()["data"]
    assert all(log["action"] == "account.create" for log in logs)
    assert len(logs) > 0


@pytest.mark.asyncio
async def test_audit_log_requires_admin(client: AsyncClient) -> None:
    """Audit logs should require auth."""
    res = await client.get("/api/v1/audit-logs")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_pagination(client: AsyncClient, auth_headers: dict) -> None:
    """Audit logs should support pagination."""
    res = await client.get(
        "/api/v1/audit-logs",
        headers=auth_headers,
        params={"page": 1, "size": 5},
    )
    assert res.status_code == 200
    meta = res.json()["meta"]
    assert meta["page"] == 1
    assert meta["size"] == 5
