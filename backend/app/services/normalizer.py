"""Normalizer engine — maps provider-specific assessment IDs to CIS-lite controls."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.control import Control
from app.models.finding import Finding

logger = logging.getLogger(__name__)


async def build_control_map(db: AsyncSession, provider: str = "azure") -> dict[str, uuid.UUID]:
    """Build a lookup: {provider_assessment_id: control.id}.

    Reads the provider_check_ref JSONB from each control and extracts
    the assessment ID for the given provider.
    """
    result = await db.execute(select(Control))
    controls = result.scalars().all()

    mapping: dict[str, uuid.UUID] = {}
    for ctrl in controls:
        ref = (ctrl.provider_check_ref or {}).get(provider)
        if ref:
            mapping[ref.lower()] = ctrl.id

    logger.info("Control map built: %d %s assessment IDs", len(mapping), provider)
    return mapping


def match_control(assessment_id: str, control_map: dict[str, uuid.UUID]) -> uuid.UUID | None:
    """Look up a single assessment ID against the control map."""
    return control_map.get(assessment_id.lower())


async def normalize_findings(
    db: AsyncSession,
    scan_id: uuid.UUID,
    provider: str = "azure",
) -> dict[str, int]:
    """Batch-normalize findings for a scan: set control_id where missing.

    Returns stats dict with matched/unmatched counts.
    """
    control_map = await build_control_map(db, provider)

    # Get findings from this scan that have no control_id yet,
    # eager-loading evidences needed by _extract_assessment_id
    result = await db.execute(
        select(Finding)
        .where(
            Finding.scan_id == scan_id,
            Finding.control_id.is_(None),
        )
        .options(selectinload(Finding.evidences))
    )
    findings = result.scalars().all()

    stats = {"matched": 0, "unmatched": 0, "total": len(findings)}

    for finding in findings:
        # Extract assessment ID from evidence snapshot
        assessment_id = _extract_assessment_id(finding)
        if not assessment_id:
            stats["unmatched"] += 1
            continue

        control_id = match_control(assessment_id, control_map)
        if control_id:
            finding.control_id = control_id
            stats["matched"] += 1
        else:
            stats["unmatched"] += 1

    await db.flush()
    logger.info(
        "Normalized scan %s: %d matched, %d unmatched of %d",
        scan_id,
        stats["matched"],
        stats["unmatched"],
        stats["total"],
    )
    return stats


def _extract_assessment_id(finding: Finding) -> str | None:
    """Extract the Azure assessment UUID from a finding's evidence snapshot.

    The Azure Resource Graph assessment ID is embedded in the resource path:
    /subscriptions/{sub}/providers/Microsoft.Security/assessments/{uuid}/...

    It's also stored as the 'name' field in the evidence snapshot.
    """
    for evidence in finding.evidences:
        snapshot = evidence.snapshot or {}
        # The Resource Graph 'name' field is the assessment UUID
        name = snapshot.get("name")
        if name:
            return name
        # Fallback: try to parse from resource ID
        resource_id = snapshot.get("resourceDetails", {}).get("Id", "")
        if "/assessments/" in resource_id:
            parts = resource_id.split("/assessments/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
    return None
