"""Tests for finding timeline (GET /findings/{id}/timeline) and
bulk-waive (POST /findings/bulk-waive) endpoints.

Coverage:
  Timeline  — empty list, event after comment, 404, tenant isolation, auth guard
  Bulk-waive — success, empty IDs, missing/empty reason, tenant isolation, auth guard,
               idempotency (already-waived findings are skipped)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.control import Control
from app.models.finding import Finding

# ── Shared helpers ────────────────────────────────────────────────────


async def _create_account(client: AsyncClient, headers: dict) -> str:
    """Create a cloud account via API and return its id."""
    res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "provider": "azure",
            "display_name": "Timeline Test Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert res.status_code == 201
    return res.json()["data"]["id"]


async def _create_finding(db: AsyncSession, account_id: str) -> str:
    """Insert an asset + control + finding directly and return the finding id."""
    asset = Asset(
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}",
        resource_type="Microsoft.Compute/virtualMachines",
        name=f"vm-timeline-{uuid.uuid4().hex[:6]}",
        region="westeurope",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    control = Control(
        code=f"CIS-TL-{uuid.uuid4().hex[:4]}",
        name="Timeline Test Control",
        description="A timeline test control",
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
        title="Timeline test finding",
        dedup_key=f"timeline:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(finding)
    await db.commit()
    return str(finding.id)


# ── Timeline tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_timeline_empty(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """A brand-new finding has no timeline events."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    res = await client.get(f"/api/v1/findings/{finding_id}/timeline", headers=auth_headers)

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert body["data"] == []


@pytest.mark.asyncio
async def test_get_timeline_after_comment(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Adding a comment records a 'commented' timeline event visible on the timeline."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Post a comment — this triggers record_event(event_type="commented")
    comment_res = await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "Investigating this finding"},
    )
    assert comment_res.status_code == 201

    res = await client.get(f"/api/v1/findings/{finding_id}/timeline", headers=auth_headers)
    assert res.status_code == 200

    events = res.json()["data"]
    assert len(events) == 1

    event = events[0]
    assert event["event_type"] == "commented"
    # The details field stores the first 200 chars of the comment content
    assert event["details"] == "Investigating this finding"
    assert event["user_id"] is not None
    assert "id" in event
    assert "created_at" in event


@pytest.mark.asyncio
async def test_get_timeline_returns_events_newest_first(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    """Timeline is ordered newest-first (created_at DESC)."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

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

    res = await client.get(f"/api/v1/findings/{finding_id}/timeline", headers=auth_headers)
    assert res.status_code == 200

    events = res.json()["data"]
    assert len(events) == 2
    # Newest event first: "Second comment" should come before "First comment"
    assert events[0]["details"] == "Second comment"
    assert events[1]["details"] == "First comment"


@pytest.mark.asyncio
async def test_get_timeline_event_schema(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Each timeline event has the required fields from FindingEventResponse."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "Schema check comment"},
    )

    res = await client.get(f"/api/v1/findings/{finding_id}/timeline", headers=auth_headers)
    assert res.status_code == 200

    event = res.json()["data"][0]
    required_fields = {"id", "event_type", "created_at"}
    for field in required_fields:
        assert field in event, f"Missing field: {field}"

    optional_fields = {"old_value", "new_value", "user_id", "user_email", "details"}
    for field in optional_fields:
        assert field in event, f"Missing optional field: {field}"


@pytest.mark.asyncio
async def test_get_timeline_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """Returns 404 for a finding that does not exist."""
    non_existent_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/findings/{non_existent_id}/timeline", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_timeline_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db: AsyncSession,
) -> None:
    """Tenant B cannot read the timeline of a finding owned by Tenant A.

    The client accumulates cookies from both registrations, so cookies are
    cleared before each cross-tenant request to ensure the Authorization
    header is the sole credential.
    """
    client.cookies.clear()
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Add an event so the timeline is non-empty for tenant A
    client.cookies.clear()
    await client.post(
        f"/api/v1/findings/{finding_id}/comments",
        headers=auth_headers,
        json={"content": "Tenant A private comment"},
    )

    # Tenant B tries to read the timeline
    client.cookies.clear()
    res = await client.get(
        f"/api/v1/findings/{finding_id}/timeline",
        headers=second_auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_timeline_requires_auth(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Unauthenticated request to timeline returns 401."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Clear cookies so no implicit authentication is sent
    client.cookies.clear()
    res = await client.get(f"/api/v1/findings/{finding_id}/timeline")
    assert res.status_code == 401


# ── Bulk-waive tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_waive_success(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Valid bulk-waive request creates Exception_ records and returns correct counts."""
    account_id = await _create_account(client, auth_headers)
    finding_id_1 = await _create_finding(db, account_id)
    finding_id_2 = await _create_finding(db, account_id)

    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={
            "finding_ids": [finding_id_1, finding_id_2],
            "reason": "Accepted risk for these findings in dev environment",
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None

    data = body["data"]
    assert data["processed"] == 2
    assert data["skipped"] == 0


@pytest.mark.asyncio
async def test_bulk_waive_records_timeline_events(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Each waived finding gets a 'waiver_requested' timeline event."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={
            "finding_ids": [finding_id],
            "reason": "Bulk waive timeline check",
        },
    )

    res = await client.get(f"/api/v1/findings/{finding_id}/timeline", headers=auth_headers)
    assert res.status_code == 200

    events = res.json()["data"]
    assert len(events) == 1
    assert events[0]["event_type"] == "waiver_requested"
    assert events[0]["new_value"] == "requested"
    assert events[0]["details"] == "Bulk waive timeline check"


@pytest.mark.asyncio
async def test_bulk_waive_skips_already_waived(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Findings with an existing active exception are skipped (not duplicated)."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # First waive
    first_res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": [finding_id], "reason": "First waive"},
    )
    assert first_res.status_code == 200
    assert first_res.json()["data"]["processed"] == 1

    # Second waive on the same finding — should be skipped
    second_res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": [finding_id], "reason": "Duplicate waive attempt"},
    )
    assert second_res.status_code == 200
    data = second_res.json()["data"]
    assert data["processed"] == 0
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_bulk_waive_mixed_new_and_already_waived(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
) -> None:
    """When some findings are already waived, counts reflect the real split."""
    account_id = await _create_account(client, auth_headers)
    finding_id_already = await _create_finding(db, account_id)
    finding_id_new = await _create_finding(db, account_id)

    # Pre-waive the first finding
    await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": [finding_id_already], "reason": "Pre-waived"},
    )

    # Bulk waive both — one new, one already waived
    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={
            "finding_ids": [finding_id_already, finding_id_new],
            "reason": "Mixed waive",
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["processed"] == 1
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_bulk_waive_empty_ids(client: AsyncClient, auth_headers: dict) -> None:
    """Submitting an empty finding_ids list returns 400."""
    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": [], "reason": "Some reason"},
    )
    assert res.status_code == 400
    assert "No finding IDs provided" in res.json()["detail"]


@pytest.mark.asyncio
async def test_bulk_waive_missing_reason(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Request body without the 'reason' field fails Pydantic validation (422)."""
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": [finding_id]},  # reason is absent
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_bulk_waive_missing_finding_ids(client: AsyncClient, auth_headers: dict) -> None:
    """Request body without the 'finding_ids' field fails Pydantic validation (422)."""
    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"reason": "Missing IDs field"},  # finding_ids is absent
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_bulk_waive_invalid_finding_id_format(client: AsyncClient, auth_headers: dict) -> None:
    """Non-UUID values in finding_ids fail Pydantic validation (422)."""
    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": ["not-a-valid-uuid"], "reason": "Bad ID format"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_bulk_waive_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db: AsyncSession,
) -> None:
    """Tenant B cannot waive findings that belong to Tenant A.

    The endpoint silently excludes IDs that don't belong to the requesting
    tenant (not a 404), resulting in processed=0 and skipped counting
    only the IDs that passed the tenant filter (none of them do).
    """
    client.cookies.clear()
    account_id = await _create_account(client, auth_headers)
    finding_id = await _create_finding(db, account_id)

    # Tenant B tries to waive Tenant A's finding
    client.cookies.clear()
    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=second_auth_headers,
        json={
            "finding_ids": [finding_id],
            "reason": "Cross-tenant waive attempt",
        },
    )

    assert res.status_code == 200
    data = res.json()["data"]
    # The ID was silently excluded because it doesn't belong to tenant B
    assert data["processed"] == 0


@pytest.mark.asyncio
async def test_bulk_waive_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated request to bulk-waive returns 401."""
    client.cookies.clear()
    res = await client.post(
        "/api/v1/findings/bulk-waive",
        json={
            "finding_ids": [str(uuid.uuid4())],
            "reason": "Unauthorized attempt",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_bulk_waive_nonexistent_finding_ids(client: AsyncClient, auth_headers: dict) -> None:
    """Finding IDs that do not exist in the tenant produce processed=0 (silent skip).

    This is the same behaviour as the tenant isolation case: the endpoint
    silently ignores IDs that fail the tenant-ownership check rather than
    raising a 404.
    """
    fake_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    res = await client.post(
        "/api/v1/findings/bulk-waive",
        headers=auth_headers,
        json={"finding_ids": fake_ids, "reason": "Waiving non-existent findings"},
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["processed"] == 0
