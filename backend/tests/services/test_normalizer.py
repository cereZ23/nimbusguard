"""Tests for the normalizer engine — maps provider assessment IDs to CIS-lite controls."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control import Control
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.services.normalizer import (
    _extract_assessment_id,
    build_control_map,
    match_control,
    normalize_findings,
)


@pytest.mark.asyncio
async def test_build_control_map(db: AsyncSession) -> None:
    ctrl = Control(
        code="CIS-AZ-01",
        name="MFA for privileged users",
        description="MFA check",
        severity="high",
        provider_check_ref={"azure": "151e82c5-5341-a74b-1eb0-bc38d2c84bb5"},
    )
    db.add(ctrl)
    await db.flush()

    mapping = await build_control_map(db, "azure")
    assert len(mapping) >= 1
    assert mapping["151e82c5-5341-a74b-1eb0-bc38d2c84bb5"] == ctrl.id


@pytest.mark.asyncio
async def test_build_control_map_case_insensitive(db: AsyncSession) -> None:
    ctrl = Control(
        code="CIS-AZ-99",
        name="Test",
        description="Test",
        severity="medium",
        provider_check_ref={"azure": "ABCD-1234"},
    )
    db.add(ctrl)
    await db.flush()

    mapping = await build_control_map(db, "azure")
    assert "abcd-1234" in mapping


@pytest.mark.asyncio
async def test_build_control_map_no_provider(db: AsyncSession) -> None:
    ctrl = Control(
        code="CIS-AZ-98",
        name="Test",
        description="Test",
        severity="low",
        provider_check_ref={"aws": "some-rule"},
    )
    db.add(ctrl)
    await db.flush()

    mapping = await build_control_map(db, "azure")
    assert len(mapping) == 0


def test_match_control_found() -> None:
    control_map = {"abc-123": uuid.uuid4(), "def-456": uuid.uuid4()}
    assert match_control("ABC-123", control_map) == control_map["abc-123"]


def test_match_control_not_found() -> None:
    control_map = {"abc-123": uuid.uuid4()}
    assert match_control("xyz-999", control_map) is None


async def _create_tenant_and_account(db: AsyncSession, suffix: str = "") -> tuple:
    """Helper to create a tenant + cloud account for normalizer tests."""
    from app.models.cloud_account import CloudAccount
    from app.models.tenant import Tenant

    tenant = Tenant(name=f"Test Tenant {suffix}", slug=f"test-tenant-{suffix or uuid.uuid4().hex[:6]}")
    db.add(tenant)
    await db.flush()

    account = CloudAccount(
        tenant_id=tenant.id,
        provider="azure",
        display_name=f"Test {suffix}",
        provider_account_id=f"sub-{uuid.uuid4().hex[:8]}",
        credential_ref="encrypted",
    )
    db.add(account)
    await db.flush()
    return tenant, account


@pytest.mark.asyncio
async def test_normalize_findings_matches(db: AsyncSession) -> None:
    from app.models.scan import Scan

    _, account = await _create_tenant_and_account(db, "match")

    scan = Scan(cloud_account_id=account.id, scan_type="full", status="running")
    db.add(scan)
    await db.flush()

    ctrl = Control(
        code="CIS-AZ-TEST",
        name="Test Control",
        description="Test",
        severity="high",
        provider_check_ref={"azure": "assess-uuid-001"},
    )
    db.add(ctrl)
    await db.flush()

    finding = Finding(
        cloud_account_id=account.id,
        scan_id=scan.id,
        status="fail",
        severity="high",
        title="Test Finding",
        dedup_key=f"azure:res:{uuid.uuid4().hex}",
    )
    db.add(finding)
    await db.flush()

    evidence = Evidence(
        finding_id=finding.id,
        snapshot={"name": "assess-uuid-001", "displayName": "Test Finding"},
    )
    db.add(evidence)
    await db.commit()

    stats = await normalize_findings(db, scan.id)
    assert stats["matched"] == 1
    assert stats["unmatched"] == 0

    await db.refresh(finding)
    assert finding.control_id == ctrl.id


@pytest.mark.asyncio
async def test_normalize_findings_no_match(db: AsyncSession) -> None:
    from app.models.scan import Scan

    _, account = await _create_tenant_and_account(db, "nomatch")

    scan = Scan(cloud_account_id=account.id, scan_type="full", status="running")
    db.add(scan)
    await db.flush()

    finding = Finding(
        cloud_account_id=account.id,
        scan_id=scan.id,
        status="fail",
        severity="medium",
        title="Unmatched Finding",
        dedup_key=f"azure:res:{uuid.uuid4().hex}",
    )
    db.add(finding)
    await db.flush()

    evidence = Evidence(
        finding_id=finding.id,
        snapshot={"name": "unknown-uuid", "displayName": "Unknown"},
    )
    db.add(evidence)
    await db.commit()

    stats = await normalize_findings(db, scan.id)
    assert stats["matched"] == 0
    assert stats["unmatched"] == 1


@pytest.mark.asyncio
async def test_normalize_skips_already_mapped(db: AsyncSession) -> None:
    from app.models.scan import Scan

    _, account = await _create_tenant_and_account(db, "skip")

    scan = Scan(cloud_account_id=account.id, scan_type="full", status="running")
    db.add(scan)
    await db.flush()

    ctrl = Control(
        code="CIS-AZ-SKIP",
        name="Skip test",
        description="Already mapped",
        severity="low",
    )
    db.add(ctrl)
    await db.flush()

    finding = Finding(
        cloud_account_id=account.id,
        scan_id=scan.id,
        control_id=ctrl.id,
        status="pass",
        severity="low",
        title="Already Mapped",
        dedup_key=f"azure:res:{uuid.uuid4().hex}",
    )
    db.add(finding)
    await db.commit()

    stats = await normalize_findings(db, scan.id)
    assert stats["total"] == 0


def test_extract_assessment_id_from_name() -> None:
    fake_evidence = SimpleNamespace(snapshot={"name": "my-assess-uuid", "displayName": "Test"})
    fake_finding = SimpleNamespace(evidences=[fake_evidence])
    result = _extract_assessment_id(fake_finding)
    assert result == "my-assess-uuid"


def test_extract_assessment_id_from_resource_path() -> None:
    fake_evidence = SimpleNamespace(
        snapshot={
            "resourceDetails": {"Id": "/subscriptions/x/providers/Microsoft.Security/assessments/abcd-1234/subpath"}
        }
    )
    fake_finding = SimpleNamespace(evidences=[fake_evidence])
    result = _extract_assessment_id(fake_finding)
    assert result == "abcd-1234"


def test_extract_assessment_id_empty() -> None:
    fake_finding = SimpleNamespace(evidences=[])
    result = _extract_assessment_id(fake_finding)
    assert result is None
