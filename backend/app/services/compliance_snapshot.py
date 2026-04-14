"""Service for capturing and querying compliance score snapshots over time."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloud_account import CloudAccount
from app.models.compliance_snapshot import ComplianceSnapshot
from app.models.control import Control
from app.models.finding import Finding

logger = logging.getLogger(__name__)

# Frameworks to snapshot.  "cis_azure" maps to Control.framework == "cis-lite".
# The others are derived from Control.framework_mappings JSONB keys.
SNAPSHOT_FRAMEWORKS = ["cis_azure", "soc2", "nist", "iso27001"]

# Mapping from snapshot framework name to the key used inside framework_mappings
_MAPPING_KEY = {
    "soc2": "soc2",
    "nist": "nist",
    "iso27001": "iso27001",
}


async def capture_compliance_snapshot(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    cloud_account_id: uuid.UUID | None = None,
) -> list[ComplianceSnapshot]:
    """Calculate current compliance scores and store snapshots for all frameworks.

    Idempotent per (tenant_id, framework, snapshot_date) — updates existing
    rows if they already exist for today.

    Returns the list of created/updated snapshot rows.
    """
    today = date.today()
    snapshots: list[ComplianceSnapshot] = []

    # Load all controls
    controls_result = await db.execute(select(Control))
    all_controls = controls_result.scalars().all()

    # Load all findings for this tenant (fail/pass with a control)
    accounts_result = await db.execute(select(CloudAccount.id).where(CloudAccount.tenant_id == tenant_id))
    account_ids = [row[0] for row in accounts_result.all()]

    if not account_ids:
        logger.debug("No cloud accounts for tenant %s, skipping snapshots", tenant_id)
        return snapshots

    findings_result = await db.execute(
        select(Finding.control_id, Finding.status).where(
            Finding.cloud_account_id.in_(account_ids),
            Finding.control_id.is_not(None),
        )
    )
    all_findings = findings_result.all()

    # Build a map: control_id -> list of statuses
    findings_by_control: dict[uuid.UUID, list[str]] = {}
    for control_id, status in all_findings:
        findings_by_control.setdefault(control_id, []).append(status)

    for framework in SNAPSHOT_FRAMEWORKS:
        # Determine which controls belong to this framework
        framework_control_ids: set[uuid.UUID] = set()
        if framework == "cis_azure":
            for ctrl in all_controls:
                if ctrl.framework == "cis-lite":
                    framework_control_ids.add(ctrl.id)
        else:
            mapping_key = _MAPPING_KEY.get(framework, framework)
            for ctrl in all_controls:
                mappings = ctrl.framework_mappings or {}
                if mapping_key in mappings and mappings[mapping_key]:
                    framework_control_ids.add(ctrl.id)

        if not framework_control_ids:
            continue

        # Calculate pass/fail per control
        passing = 0
        failing = 0
        for ctrl_id in framework_control_ids:
            statuses = findings_by_control.get(ctrl_id, [])
            if not statuses:
                # No findings means no data — count as neither pass nor fail
                continue
            has_fail = any(s == "fail" for s in statuses)
            if has_fail:
                failing += 1
            else:
                passing += 1

        total = passing + failing
        score = round((passing / total) * 100, 1) if total > 0 else 0.0

        # Upsert: check if snapshot already exists for today
        existing_result = await db.execute(
            select(ComplianceSnapshot).where(
                ComplianceSnapshot.tenant_id == tenant_id,
                ComplianceSnapshot.framework == framework,
                ComplianceSnapshot.snapshot_date == today,
            )
        )
        snapshot = existing_result.scalar_one_or_none()

        if snapshot:
            snapshot.score = score
            snapshot.total_controls = total
            snapshot.passing_controls = passing
            snapshot.failing_controls = failing
            snapshot.cloud_account_id = cloud_account_id
        else:
            snapshot = ComplianceSnapshot(
                tenant_id=tenant_id,
                framework=framework,
                score=score,
                total_controls=total,
                passing_controls=passing,
                failing_controls=failing,
                snapshot_date=today,
                cloud_account_id=cloud_account_id,
            )
            db.add(snapshot)

        snapshots.append(snapshot)

    await db.flush()
    logger.info(
        "Compliance snapshots captured for tenant %s: %d frameworks",
        tenant_id,
        len(snapshots),
    )
    return snapshots


async def get_compliance_trend(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    framework: str = "cis_azure",
    days: int = 30,
) -> list[ComplianceSnapshot]:
    """Retrieve compliance trend data for a tenant and framework over a period."""
    since = datetime.now(UTC).date() - timedelta(days=days)

    result = await db.execute(
        select(ComplianceSnapshot)
        .where(
            ComplianceSnapshot.tenant_id == tenant_id,
            ComplianceSnapshot.framework == framework,
            ComplianceSnapshot.snapshot_date >= since,
        )
        .order_by(ComplianceSnapshot.snapshot_date)
    )
    return list(result.scalars().all())
