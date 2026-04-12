"""Tests for cursor-paginated sub-collections on `/findings/{id}`.

Covers:
    - `GET /findings/{id}/timeline` — default limit, has_more, before cursor
    - `GET /findings/{id}/comments` — default limit, has_more, before cursor
    - `GET /findings/{id}/evidence`  — new endpoint, plus `total_evidence_count`
                                        on the detail response
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.models.finding_comment import FindingComment
from app.models.finding_event import FindingEvent
from app.models.user import User


async def _get_first_user_id(db: AsyncSession) -> uuid.UUID:
    """Fetch the single user the auth_headers fixture created."""
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one()
    return user.id


async def _create_account(client: AsyncClient, auth_headers: dict) -> str:
    res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": f"PageTest {uuid.uuid4().hex[:6]}",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _create_finding(db: AsyncSession, account_id: str) -> uuid.UUID:
    account = await db.get(CloudAccount, uuid.UUID(account_id))
    assert account is not None

    asset = Asset(
        tenant_id=account.tenant_id,
        cloud_account_id=account.id,
        provider_id=f"/subscriptions/sub-test/vm/{uuid.uuid4().hex[:6]}",
        resource_type="microsoft.compute/virtualmachines",
        name=f"vm-{uuid.uuid4().hex[:6]}",
        region="westeurope",
        raw_properties={},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    control = Control(
        code=f"CIS-TEST-{uuid.uuid4().hex[:4]}",
        name="Pagination test control",
        description="Pagination test",
        severity="medium",
        framework="cis-lite",
    )
    db.add_all([asset, control])
    await db.flush()

    finding = Finding(
        tenant_id=account.tenant_id,
        cloud_account_id=account.id,
        asset_id=asset.id,
        control_id=control.id,
        status="fail",
        severity="medium",
        title="Pagination test finding",
        dedup_key=f"pagination:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(finding)
    await db.commit()
    return finding.id


# ── Timeline ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeline_default_limit_caps_at_20(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    base_time = datetime.now(UTC) - timedelta(days=30)
    for i in range(35):
        db.add(
            FindingEvent(
                finding_id=finding_id,
                event_type="rescanned",
                details=f"event {i}",
                created_at=base_time + timedelta(minutes=i),
            )
        )
    await db.commit()

    res = await client.get(f"/api/v1/findings/{finding_id}/timeline", headers=auth_headers)
    assert res.status_code == 200
    payload = res.json()
    assert len(payload["data"]) == 20
    assert payload["meta"]["total"] == 35
    assert payload["meta"]["limit"] == 20
    assert payload["meta"]["has_more"] is True
    assert payload["meta"]["next_cursor"] is not None
    # Newest-first — the latest row has the highest minute offset.
    assert payload["data"][0]["details"] == "event 34"


@pytest.mark.asyncio
async def test_timeline_cursor_loads_older_page(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    base_time = datetime.now(UTC) - timedelta(days=30)
    for i in range(25):
        db.add(
            FindingEvent(
                finding_id=finding_id,
                event_type="rescanned",
                details=f"event {i}",
                created_at=base_time + timedelta(minutes=i),
            )
        )
    await db.commit()

    # First page
    first = await client.get(
        f"/api/v1/findings/{finding_id}/timeline?limit=20",
        headers=auth_headers,
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert len(first_payload["data"]) == 20
    assert first_payload["meta"]["has_more"] is True
    cursor = first_payload["meta"]["next_cursor"]

    # Second page via cursor — should return the remaining 5 oldest events.
    # URL-encode the cursor because ISO timestamps contain `+`.
    second = await client.get(
        f"/api/v1/findings/{finding_id}/timeline?limit=20&before={quote_plus(cursor)}",
        headers=auth_headers,
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert len(second_payload["data"]) == 5
    assert second_payload["meta"]["has_more"] is False
    assert second_payload["meta"]["next_cursor"] is None
    # No overlap between the two pages.
    first_ids = {row["id"] for row in first_payload["data"]}
    second_ids = {row["id"] for row in second_payload["data"]}
    assert first_ids.isdisjoint(second_ids)


# ── Comments ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_comments_default_limit_caps_and_has_more(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)
    user_id = await _get_first_user_id(db)

    base_time = datetime.now(UTC) - timedelta(days=30)
    for i in range(25):
        db.add(
            FindingComment(
                finding_id=finding_id,
                user_id=user_id,
                content=f"comment {i}",
                created_at=base_time + timedelta(minutes=i),
            )
        )
    await db.commit()

    res = await client.get(f"/api/v1/findings/{finding_id}/comments?limit=20", headers=auth_headers)
    assert res.status_code == 200
    payload = res.json()
    assert len(payload["data"]) == 20
    assert payload["meta"]["total"] == 25
    assert payload["meta"]["has_more"] is True
    # Newest first.
    assert payload["data"][0]["content"] == "comment 24"


# ── Evidence ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finding_detail_returns_only_latest_evidence(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    """Detail endpoint must embed at most 1 evidence row."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    base_time = datetime.now(UTC) - timedelta(days=30)
    for i in range(10):
        db.add(
            Evidence(
                finding_id=finding_id,
                snapshot={"i": i},
                collected_at=base_time + timedelta(hours=i),
            )
        )
    await db.commit()

    res = await client.get(f"/api/v1/findings/{finding_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    # Only the latest evidence row is embedded.
    assert len(data["evidences"]) == 1
    assert data["evidences"][0]["snapshot"] == {"i": 9}
    # Total count lets the UI show a "+9 more" badge.
    assert data["total_evidence_count"] == 10


@pytest.mark.asyncio
async def test_evidence_endpoint_is_paginated(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    base_time = datetime.now(UTC) - timedelta(days=30)
    for i in range(25):
        db.add(
            Evidence(
                finding_id=finding_id,
                snapshot={"i": i},
                collected_at=base_time + timedelta(hours=i),
            )
        )
    await db.commit()

    res = await client.get(f"/api/v1/findings/{finding_id}/evidence?limit=20", headers=auth_headers)
    assert res.status_code == 200
    payload = res.json()
    assert len(payload["data"]) == 20
    assert payload["meta"]["total"] == 25
    assert payload["meta"]["has_more"] is True
    cursor = payload["meta"]["next_cursor"]
    assert cursor is not None

    # Older page — should return 5. URL-encode cursor for the `+` in ISO.
    older = await client.get(
        f"/api/v1/findings/{finding_id}/evidence?limit=20&before={quote_plus(cursor)}",
        headers=auth_headers,
    )
    assert older.status_code == 200
    older_payload = older.json()
    assert len(older_payload["data"]) == 5
    assert older_payload["meta"]["has_more"] is False
