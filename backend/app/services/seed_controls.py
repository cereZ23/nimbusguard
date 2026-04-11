"""Seed CIS-lite controls from YAML mapping file into the database."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control import Control
from app.services.priority import default_effort, default_exposure

logger = logging.getLogger(__name__)

MAPPINGS_FILE = Path(__file__).parent.parent / "config" / "control_mappings.yaml"


def _resource_type_for_control(code: str) -> str | None:
    """Return the first resource_type that has an @check decorator registered
    for the given CIS code, or None if the control isn't yet linked to an
    evaluator.

    Used to infer a sensible ``default_exposure()`` fallback when the yaml
    doesn't carry an explicit ``exposure`` field. We import the registry
    lazily to avoid a circular import at module load time.
    """
    from app.services.evaluator import registry

    for (resource_type, control_code), _fn in registry.all_checks.items():
        if control_code == code:
            return resource_type
    return None


def _resolve_effort(ctrl: dict) -> str:
    """Return an explicit yaml ``effort`` value, or an inferred default."""
    explicit = ctrl.get("effort")
    if isinstance(explicit, str) and explicit.lower() in ("quick", "moderate", "refactor"):
        return explicit.lower()
    return default_effort(ctrl.get("name"))


def _resolve_exposure(ctrl: dict) -> str:
    """Return an explicit yaml ``exposure`` value, or an inferred default
    based on the resource type the control's evaluator is registered on."""
    explicit = ctrl.get("exposure")
    if isinstance(explicit, str) and explicit.lower() in ("internet", "internal", "none"):
        return explicit.lower()
    resource_type = _resource_type_for_control(ctrl.get("code", ""))
    return default_exposure(resource_type)


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
        effort = _resolve_effort(ctrl)
        exposure = _resolve_exposure(ctrl)
        remediation_group = ctrl.get("remediation_group")
        remediation_action = ctrl.get("remediation_action")

        if control:
            control.name = ctrl["name"]
            control.description = ctrl["description"]
            control.severity = ctrl["severity"]
            control.framework = ctrl.get("framework", "cis-lite")
            control.remediation_hint = ctrl.get("remediation_hint")
            control.provider_check_ref = ctrl.get("provider_check_ref", {})
            control.framework_mappings = framework_mappings
            control.effort = effort
            control.exposure = exposure
            control.remediation_group = remediation_group
            control.remediation_action = remediation_action
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
                effort=effort,
                exposure=exposure,
                remediation_group=remediation_group,
                remediation_action=remediation_action,
            )
            db.add(control)

        count += 1

    await db.commit()
    logger.info("Seeded %d controls with priority metadata", count)
    return count
