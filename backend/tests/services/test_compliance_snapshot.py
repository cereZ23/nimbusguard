"""Unit tests for app.services.compliance_snapshot.

Builds tenants/accounts/controls/findings directly via the db fixture and
asserts the per-framework pass/fail aggregation, upsert idempotency, the
no-accounts short-circuit, and the trend query.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.cloud_account import CloudAccount
from app.models.compliance_snapshot import ComplianceSnapshot
from app.models.control import Control
from app.models.finding import Finding
from app.models.tenant import Tenant
from app.services.compliance_snapshot import (
    capture_compliance_snapshot,
    get_compliance_trend,
)


async def _tenant(db) -> Tenant:
    t = Tenant(name="CS Tenant", slug=f"cs-{uuid.uuid4().hex[:8]}")
    db.add(t)
    await db.flush()
    return t


async def _account(db, tenant_id) -> CloudAccount:
    acc = CloudAccount(
        tenant_id=tenant_id,
        provider="azure",
        display_name="acc",
        provider_account_id=f"sub-{uuid.uuid4().hex[:8]}",
        credential_ref="x",
    )
    db.add(acc)
    await db.flush()
    return acc


async def _control(db, *, framework="cis-lite", mappings=None) -> Control:
    c = Control(
        code=f"C-{uuid.uuid4().hex[:8]}",
        name="ctrl",
        description="desc",
        severity="high",
        framework=framework,
        framework_mappings=mappings or {},
    )
    db.add(c)
    await db.flush()
    return c


async def _finding(db, *, tenant_id, account_id, control_id, status):
    f = Finding(
        tenant_id=tenant_id,
        cloud_account_id=account_id,
        control_id=control_id,
        status=status,
        severity="high",
        title="f",
        dedup_key=f"d:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(f)
    await db.flush()
    return f


# ── no accounts short-circuit ────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_accounts_returns_empty(db):
    t = await _tenant(db)
    result = await capture_compliance_snapshot(db, t.id)
    assert result == []


# ── cis_azure aggregation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cis_azure_pass_fail_aggregation(db):
    t = await _tenant(db)
    acc = await _account(db, t.id)

    c_pass = await _control(db, framework="cis-lite")
    c_fail = await _control(db, framework="cis-lite")
    c_nodata = await _control(db, framework="cis-lite")  # no findings -> ignored

    # passing control: only pass findings
    await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c_pass.id, status="pass")
    # failing control: at least one fail (mixed)
    await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c_fail.id, status="pass")
    await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c_fail.id, status="fail")

    snaps = await capture_compliance_snapshot(db, t.id)
    by_fw = {s.framework: s for s in snaps}

    assert "cis_azure" in by_fw
    cis = by_fw["cis_azure"]
    assert cis.total_controls == 2  # c_nodata excluded
    assert cis.passing_controls == 1
    assert cis.failing_controls == 1
    assert cis.score == 50.0


# ── framework_mappings based frameworks ──────────────────────────────


@pytest.mark.asyncio
async def test_mapping_based_framework(db):
    t = await _tenant(db)
    acc = await _account(db, t.id)

    # control mapped to soc2 + nist, all-pass
    c = await _control(db, framework="cis-lite", mappings={"soc2": ["CC6.1"], "nist": ["AC-2"]})
    await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c.id, status="pass")

    # control mapped to soc2 only, failing; iso27001 left with empty mapping -> skipped
    c2 = await _control(db, framework="cis-lite", mappings={"soc2": ["CC7.1"], "iso27001": []})
    await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c2.id, status="fail")

    snaps = await capture_compliance_snapshot(db, t.id)
    by_fw = {s.framework: s for s in snaps}

    # soc2: 2 controls, 1 pass / 1 fail
    assert by_fw["soc2"].total_controls == 2
    assert by_fw["soc2"].passing_controls == 1
    assert by_fw["soc2"].failing_controls == 1
    assert by_fw["soc2"].score == 50.0

    # nist: 1 control, all pass -> 100
    assert by_fw["nist"].total_controls == 1
    assert by_fw["nist"].score == 100.0

    # iso27001 had only an empty mapping list -> no controls -> not produced
    assert "iso27001" not in by_fw


# ── idempotent upsert ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_updates_existing_row(db):
    t = await _tenant(db)
    acc = await _account(db, t.id)
    c = await _control(db, framework="cis-lite")
    f = await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c.id, status="fail")

    snaps1 = await capture_compliance_snapshot(db, t.id)
    cis1 = next(s for s in snaps1 if s.framework == "cis_azure")
    assert cis1.failing_controls == 1
    assert cis1.score == 0.0
    first_id = cis1.id

    # flip the finding to pass and recompute today's snapshot
    f.status = "pass"
    await db.flush()

    snaps2 = await capture_compliance_snapshot(db, t.id)
    cis2 = next(s for s in snaps2 if s.framework == "cis_azure")

    # same row id (upsert, not insert), updated numbers
    assert cis2.id == first_id
    assert cis2.passing_controls == 1
    assert cis2.score == 100.0

    # exactly one row in DB for cis_azure today
    rows = (
        await db.execute(
            select(ComplianceSnapshot).where(
                ComplianceSnapshot.tenant_id == t.id,
                ComplianceSnapshot.framework == "cis_azure",
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_capture_with_cloud_account_id_set(db):
    t = await _tenant(db)
    acc = await _account(db, t.id)
    c = await _control(db, framework="cis-lite")
    await _finding(db, tenant_id=t.id, account_id=acc.id, control_id=c.id, status="pass")

    snaps = await capture_compliance_snapshot(db, t.id, cloud_account_id=acc.id)
    cis = next(s for s in snaps if s.framework == "cis_azure")
    assert cis.cloud_account_id == acc.id


# ── trend query ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_compliance_trend(db):
    t = await _tenant(db)
    today = date.today()

    # in-window + out-of-window snapshots
    recent = ComplianceSnapshot(
        tenant_id=t.id, framework="cis_azure", score=80.0,
        total_controls=10, passing_controls=8, failing_controls=2,
        snapshot_date=today - timedelta(days=5),
    )
    old = ComplianceSnapshot(
        tenant_id=t.id, framework="cis_azure", score=50.0,
        total_controls=10, passing_controls=5, failing_controls=5,
        snapshot_date=today - timedelta(days=90),
    )
    other_fw = ComplianceSnapshot(
        tenant_id=t.id, framework="soc2", score=90.0,
        total_controls=10, passing_controls=9, failing_controls=1,
        snapshot_date=today,
    )
    db.add_all([recent, old, other_fw])
    await db.flush()

    trend = await get_compliance_trend(db, t.id, framework="cis_azure", days=30)
    assert len(trend) == 1
    assert trend[0].score == 80.0

    # wider window picks up the old one too, ordered by date
    trend_all = await get_compliance_trend(db, t.id, framework="cis_azure", days=365)
    assert [s.score for s in trend_all] == [50.0, 80.0]
