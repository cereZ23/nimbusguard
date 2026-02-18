"""Tests for finding assignment (ADV-04) and comments (ADV-05)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.control import Control
from app.models.finding import Finding


# ── Helpers ──────────────────────────────────────────────────────────


async def _create_finding(db: AsyncSession, account_id: str) -> str:
    """Create a test finding and return its id."""
    asset = Asset(
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}",
        resource_type="Microsoft.Compute/virtualMachines",
        name="vm-assign-test",
        region="westeurope",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    control = Control(
        code=f"CIS-ASSIGN-{uuid.uuid4().hex[:4]}",
        name="Assignment Test Control",
        description="Test",
        severity="high",
        framework="cis-lite",
    )
    db.add_all([asset, control])
    await db.flush()

    finding = Finding(
        cloud_account_id=account_id,
        asset_id=asset.id,
        control_id=control.id,
        status="fail",
        severity="high",
        title="Assignment test finding",
        dedup_key=f"assign:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(finding)
    await db.commit()
    return str(finding.id)


async def _create_account(client: AsyncClient, headers: dict) -> str:
    """Create a cloud account via API and return its id."""
    res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "provider": "azure",
            "display_name": "Assign Test Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 201
    return res.json()["data"]["id"]


async def _get_user_id(client: AsyncClient, headers: dict) -> str:
    """Get current user id from /auth/me."""
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    return res.json()["data"]["id"]


# ── Assignment tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assign_finding(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)
    user_id = await _get_user_id(client, auth_headers)

    res = await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=auth_headers,
        json={"user_id": user_id},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["assigned_to"] == user_id
    assert data["assignee_email"] is not None
    assert data["assignee_name"] is not None


@pytest.mark.asyncio
async def test_unassign_finding(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)
    user_id = await _get_user_id(client, auth_headers)

    # Assign first
    res = await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=auth_headers,
        json={"user_id": user_id},
    )
    assert res.status_code == 200
    assert res.json()["data"]["assigned_to"] == user_id

    # Unassign
    res = await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=auth_headers,
        json={"user_id": None},
    )
    assert res.status_code == 200
    assert res.json()["data"]["assigned_to"] is None
    assert res.json()["data"]["assignee_email"] is None


@pytest.mark.asyncio
async def test_assign_finding_not_found(
    client: AsyncClient, auth_headers: dict
) -> None:
    fake_id = str(uuid.uuid4())
    user_id = await _get_user_id(client, auth_headers)

    res = await client.put(
        f"/api/v1/findings/{fake_id}/assign",
        headers=auth_headers,
        json={"user_id": user_id},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_assign_finding_invalid_user(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    res = await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=auth_headers,
        json={"user_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404
    assert "Assignee not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_assign_finding_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db: AsyncSession,
) -> None:
    """Users from another tenant cannot assign findings they don't own.

    Note: The httpx client accumulates cookies from both registrations.
    Since get_current_user checks cookies first, we clear cookies before
    making requests to ensure the Authorization header is used.
    """
    # Clear cookies so Authorization header is respected
    client.cookies.clear()
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Clear cookies again before second user request
    client.cookies.clear()
    second_user_id = await _get_user_id(client, second_auth_headers)

    # Second tenant user tries to assign a finding from first tenant
    client.cookies.clear()
    res = await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=second_auth_headers,
        json={"user_id": second_user_id},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_findings_filter_assigned_to(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)
    user_id = await _get_user_id(client, auth_headers)

    # Assign the finding
    res = await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=auth_headers,
        json={"user_id": user_id},
    )
    assert res.status_code == 200

    # Filter by assigned_to
    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"assigned_to": user_id},
    )
    assert res.status_code == 200
    assert res.json()["meta"]["total"] >= 1
    for f in res.json()["data"]:
        assert f["assigned_to"] == user_id


@pytest.mark.asyncio
async def test_get_finding_includes_assignee(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)
    user_id = await _get_user_id(client, auth_headers)

    # Assign
    await client.put(
        f"/api/v1/findings/{finding_id}/assign",
        headers=auth_headers,
        json={"user_id": user_id},
    )

    # Get detail
    res = await client.get(
        f"/api/v1/findings/{finding_id}", headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["assigned_to"] == user_id
    assert data["assignee_email"] is not None


# ── Comment tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_comment(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "This needs investigation."},
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["content"] == "This needs investigation."
    assert data["user_email"] is not None
    assert data["user_name"] is not None
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_comments(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Add two comments
    await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "First comment"},
    )
    await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "Second comment"},
    )

    res = await client.get(
        f"/api/v1/findings/{finding_id}/comments", headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 2
    assert data[0]["content"] == "First comment"
    assert data[1]["content"] == "Second comment"


@pytest.mark.asyncio
async def test_list_comments_empty(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    res = await client.get(
        f"/api/v1/findings/{finding_id}/comments", headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["data"] == []


@pytest.mark.asyncio
async def test_delete_own_comment(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Add comment
    add_res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "To be deleted"},
    )
    comment_id = add_res.json()["data"]["id"]

    # Delete it
    res = await client.delete(
        f"/api/v1/findings/{finding_id}/comments/{comment_id}",
        headers=auth_headers,
    )
    assert res.status_code == 204

    # Verify it's gone
    list_res = await client.get(
        f"/api/v1/findings/{finding_id}/comments", headers=auth_headers
    )
    assert len(list_res.json()["data"]) == 0


@pytest.mark.asyncio
async def test_delete_comment_not_found(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    fake_comment_id = str(uuid.uuid4())
    res = await client.delete(
        f"/api/v1/findings/{finding_id}/comments/{fake_comment_id}",
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_comment_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db: AsyncSession,
) -> None:
    """Users from another tenant cannot list or add comments on findings they don't own."""
    # Clear cookies so Authorization header is respected
    client.cookies.clear()
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Second tenant tries to list comments
    client.cookies.clear()
    res = await client.get(
        f"/api/v1/findings/{finding_id}/comments",
        headers=second_auth_headers,
    )
    assert res.status_code == 404

    # Second tenant tries to add a comment
    client.cookies.clear()
    res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=second_auth_headers,
        json={"content": "Unauthorized comment"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_comment_content_validation(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Empty content
    res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": ""},
    )
    assert res.status_code == 422

    # Too long content (>2000 chars)
    res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "x" * 2001},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_comment_requires_auth(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Clear cookies so that no auth is sent at all (no cookie, no header)
    client.cookies.clear()

    res = await client.get(f"/api/v1/findings/{finding_id}/comments")
    assert res.status_code == 401

    res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        json={"content": "Unauthorized"},
    )
    assert res.status_code == 401
