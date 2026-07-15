"""Integration-level tests for the m365 provider wiring:

- evaluator skips checks that return None (data not collected)
- seed_controls loads the CIS-M365 catalogue with automation metadata
- compliance snapshots include the cis_m365 framework
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.tenant import Tenant
from app.services.compliance_snapshot import capture_compliance_snapshot
from app.services.evaluator import EvalResult, check, evaluate_asset
from app.services.seed_controls import seed_controls

# ── Evaluator skip semantics ────────────────────────────────────────


def _make_asset(resource_type: str) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/test/{uuid.uuid4()}",
        resource_type=resource_type,
        name="Test",
        region="global",
        raw_properties={},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def test_evaluate_asset_skips_none_results():
    resource_type = f"test365/skip-{uuid.uuid4().hex[:8]}"

    @check(resource_type, "TEST-SKIP-NONE")
    def _skipper(asset: Asset) -> EvalResult | None:
        return None

    @check(resource_type, "TEST-SKIP-PASS")
    def _passer(asset: Asset) -> EvalResult | None:
        return EvalResult(status="pass", evidence={}, description="ok")

    try:
        fake_control = object()
        controls_by_code = {"TEST-SKIP-NONE": fake_control, "TEST-SKIP-PASS": fake_control}

        results = evaluate_asset(_make_asset(resource_type), controls_by_code)

        assert [(code, r.status) for code, r in results] == [("TEST-SKIP-PASS", "pass")]
    finally:
        # Don't leak the temp checks into the global registry — other tests
        # assert on its total size.
        from app.services.evaluator import registry

        registry._checks.pop((resource_type, "TEST-SKIP-NONE"), None)
        registry._checks.pop((resource_type, "TEST-SKIP-PASS"), None)


def test_m365_checks_skip_on_empty_asset():
    """A freshly-created m365 asset with no collected data yields zero results,
    not zero-evidence failures."""
    asset = _make_asset("microsoft365/tenant")
    fake_control = object()
    from app.services.evaluator import registry

    codes = {code for rt, code in registry.all_checks if rt == "microsoft365/tenant"}
    assert codes, "expected m365 tenant checks to be registered"
    results = evaluate_asset(asset, dict.fromkeys(codes, fake_control))
    assert results == []


# ── Seeding ─────────────────────────────────────────────────────────


async def test_seed_controls_loads_m365_catalogue(db):
    await seed_controls(db)

    result = await db.execute(select(Control).where(Control.code.like("CIS-M365-%")))
    controls = result.scalars().all()

    assert len(controls) >= 80
    by_automation = {"manual": 0, "automated": 0}
    for ctrl in controls:
        assert ctrl.framework == "cis-m365"
        assert ctrl.effort in ("quick", "moderate", "refactor")
        assert ctrl.exposure in ("internet", "internal", "none")
        by_automation[ctrl.automation] += 1
    assert by_automation["manual"] >= 30
    assert by_automation["automated"] >= 40

    # Automated controls carry an m365 provider_check_ref for documentation
    mfa = next(c for c in controls if c.code == "CIS-M365-5.2.2.1")
    assert mfa.automation == "automated"
    assert mfa.severity == "high"
    assert "m365" in mfa.provider_check_ref

    teams_manual = next(c for c in controls if c.code == "CIS-M365-8.5.3")
    assert teams_manual.automation == "manual"


async def test_seeded_automated_controls_match_registry(db):
    from app.services.evaluator import registry

    await seed_controls(db)
    result = await db.execute(
        select(Control.code).where(Control.code.like("CIS-M365-%"), Control.automation == "automated")
    )
    automated_codes = {row[0] for row in result.all()}
    registered_codes = {code for _, code in registry.all_checks if code.startswith("CIS-M365")}
    assert automated_codes == registered_codes


# ── Compliance snapshots ────────────────────────────────────────────


async def test_snapshot_includes_cis_m365_framework(db):
    await seed_controls(db)
    tenant = Tenant(name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    account = CloudAccount(
        tenant_id=tenant.id,
        provider="m365",
        display_name="M365",
        provider_account_id="tenant-guid",
        credential_ref="ref",
    )
    db.add(account)
    await db.flush()

    snapshots = await capture_compliance_snapshot(db, tenant.id)

    frameworks = {s.framework for s in snapshots}
    assert "cis_m365" in frameworks
    assert "cis_azure" in frameworks
