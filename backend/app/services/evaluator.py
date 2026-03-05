"""Evaluation engine — analyzes asset raw_properties to produce findings.

Instead of relying on Azure Defender for Cloud (which requires paid tiers),
this engine reads the raw_properties collected via Resource Graph and evaluates
them against CIS-lite controls directly.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.evidence import Evidence
from app.models.finding import Finding

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    status: str  # "pass" | "fail"
    evidence: dict = field(default_factory=dict)
    description: str = ""


CheckFn = Callable[[Asset], EvalResult]


class CheckRegistry:
    """Registry of check functions keyed by (resource_type, control_code)."""

    def __init__(self) -> None:
        self._checks: dict[tuple[str, str], CheckFn] = {}

    def register(self, resource_type: str, control_code: str, fn: CheckFn) -> None:
        self._checks[(resource_type.lower(), control_code)] = fn

    def get_checks_for(self, resource_type: str) -> list[tuple[str, CheckFn]]:
        """Return [(control_code, fn)] for the given resource type."""
        rt = resource_type.lower()
        return [(code, fn) for (check_rt, code), fn in self._checks.items() if check_rt == rt]

    @property
    def all_checks(self) -> dict[tuple[str, str], CheckFn]:
        """Return the full registry dict (for introspection/testing)."""
        return dict(self._checks)


# Global registry instance
registry = CheckRegistry()


def check(resource_type: str, control_code: str) -> Callable[[CheckFn], CheckFn]:
    """Decorator to register a check function."""

    def decorator(fn: CheckFn) -> CheckFn:
        registry.register(resource_type, control_code, fn)
        return fn

    return decorator


# Import all check modules — this triggers @check decorators and populates the registry
import app.services.aws.checks  # noqa: E402, F401
import app.services.azure.checks  # noqa: E402, F401

# ── Evaluation orchestration ─────────────────────────────────────────


def evaluate_asset(
    asset: Asset,
    controls_by_code: dict[str, Control],
) -> list[tuple[str, EvalResult]]:
    """Run all applicable checks for an asset. Returns [(control_code, result)]."""
    checks = registry.get_checks_for(asset.resource_type)
    results = []
    for control_code, fn in checks:
        if control_code not in controls_by_code:
            logger.warning("Control %s not found in DB, skipping", control_code)
            continue
        result = fn(asset)
        results.append((control_code, result))
    return results


async def evaluate_all(
    db: AsyncSession,
    cloud_account_id: uuid.UUID,
    scan_id: uuid.UUID,
) -> dict:
    """Evaluate all assets for a cloud account and create/update findings.

    Returns stats dict with pass/fail/created/updated counts.
    """
    # Load controls by code
    result = await db.execute(select(Control))
    controls_by_code = {c.code: c for c in result.scalars().all()}

    # Load assets for this account
    result = await db.execute(select(Asset).where(Asset.cloud_account_id == cloud_account_id))
    assets = result.scalars().all()

    # Batch-load all existing eval findings for this account to avoid N+1 queries.
    # The dedup_key format is "eval:{provider_id}:{control_code}" so we can match
    # by the "eval:" prefix and cloud_account_id.
    existing_findings_result = await db.execute(
        select(Finding).where(
            Finding.cloud_account_id == cloud_account_id,
            Finding.dedup_key.like("eval:%"),
        )
    )
    existing_findings_by_dedup: dict[str, Finding] = {f.dedup_key: f for f in existing_findings_result.scalars().all()}

    stats = {
        "assets_evaluated": 0,
        "checks_run": 0,
        "pass_count": 0,
        "fail_count": 0,
        "findings_created": 0,
        "findings_updated": 0,
    }
    now = datetime.now(UTC)

    # Collect new findings and evidence to flush in batches
    batch_count = 0

    for asset in assets:
        checks = evaluate_asset(asset, controls_by_code)
        if not checks:
            continue

        stats["assets_evaluated"] += 1

        for control_code, eval_result in checks:
            stats["checks_run"] += 1
            if eval_result.status == "pass":
                stats["pass_count"] += 1
            else:
                stats["fail_count"] += 1

            control = controls_by_code[control_code]
            dedup_key = f"eval:{asset.provider_id}:{control_code}"

            # Look up existing finding from pre-loaded map (no DB query)
            finding = existing_findings_by_dedup.get(dedup_key)

            if finding:
                finding.status = eval_result.status
                finding.last_evaluated_at = now
                finding.scan_id = scan_id
                stats["findings_updated"] += 1
            else:
                finding = Finding(
                    cloud_account_id=cloud_account_id,
                    asset_id=asset.id,
                    control_id=control.id,
                    scan_id=scan_id,
                    status=eval_result.status,
                    severity=control.severity,
                    title=control.name,
                    dedup_key=dedup_key,
                    first_detected_at=now,
                    last_evaluated_at=now,
                )
                db.add(finding)
                # Flush to get the finding.id for the evidence FK
                await db.flush()
                # Add to map so duplicate dedup_keys within this run are handled
                existing_findings_by_dedup[dedup_key] = finding
                stats["findings_created"] += 1

            # Create evidence snapshot
            evidence = Evidence(
                finding_id=finding.id,
                snapshot={
                    "source": "evaluation_engine",
                    "control_code": control_code,
                    "status": eval_result.status,
                    "description": eval_result.description,
                    "resource_id": asset.provider_id,
                    "resource_name": asset.name,
                    "resource_type": asset.resource_type,
                    "properties": eval_result.evidence,
                    "evaluated_at": now.isoformat(),
                },
                collected_at=now,
            )
            db.add(evidence)

            # Periodic flush to keep memory bounded on large accounts
            batch_count += 1
            if batch_count >= 200:
                await db.flush()
                batch_count = 0

    # Calculate and update secure score
    total = stats["pass_count"] + stats["fail_count"]
    if total > 0:
        score = round((stats["pass_count"] / total) * 100, 1)
        stats["secure_score"] = score

        account_result = await db.execute(select(CloudAccount).where(CloudAccount.id == cloud_account_id))
        account = account_result.scalar_one_or_none()
        if account:
            metadata = dict(account.metadata_ or {})
            metadata["secure_score"] = score
            metadata["secure_score_source"] = "evaluation_engine"
            metadata["secure_score_details"] = {
                "pass": stats["pass_count"],
                "fail": stats["fail_count"],
                "total": total,
            }
            account.metadata_ = metadata

    await db.flush()
    logger.info(
        "Evaluation complete for account %s: %d assets, %d checks, %d pass, %d fail",
        cloud_account_id,
        stats["assets_evaluated"],
        stats["checks_run"],
        stats["pass_count"],
        stats["fail_count"],
    )
    return stats
