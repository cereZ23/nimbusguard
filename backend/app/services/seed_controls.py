"""Seed CIS-lite controls from YAML mapping file into the database."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control import Control

logger = logging.getLogger(__name__)

MAPPINGS_FILE = Path(__file__).parent.parent / "config" / "control_mappings.yaml"


async def seed_controls(db: AsyncSession) -> int:
    """Load controls from YAML and upsert into database. Returns count of controls upserted."""
    with open(MAPPINGS_FILE) as f:
        data = yaml.safe_load(f)

    controls = data.get("controls", [])
    count = 0

    for ctrl in controls:
        existing = await db.execute(select(Control).where(Control.code == ctrl["code"]))
        control = existing.scalar_one_or_none()

        framework_mappings = ctrl.get("framework_mappings", {})

        if control:
            control.name = ctrl["name"]
            control.description = ctrl["description"]
            control.severity = ctrl["severity"]
            control.framework = ctrl.get("framework", "cis-lite")
            control.remediation_hint = ctrl.get("remediation_hint")
            control.provider_check_ref = ctrl.get("provider_check_ref", {})
            control.framework_mappings = framework_mappings
        else:
            control = Control(
                code=ctrl["code"],
                name=ctrl["name"],
                description=ctrl["description"],
                severity=ctrl["severity"],
                framework=ctrl.get("framework", "cis-lite"),
                remediation_hint=ctrl.get("remediation_hint"),
                provider_check_ref=ctrl.get("provider_check_ref", {}),
                framework_mappings=framework_mappings,
            )
            db.add(control)

        count += 1

    await db.commit()
    logger.info("Seeded %d controls with framework mappings", count)
    return count
