"""App Service Plan (serverfarms) checks (CIS-AZ-85..88)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# Compute modes that are NOT suitable for production workloads.
# "Shared" is the shared compute mode (Free/Shared tiers). "Dynamic" is consumption (Functions).
# Acceptable production modes: "Dedicated" (Basic/Standard/Premium) and "ElasticPremium".
_SHARED_COMPUTE_MODES = {"shared"}


@check("microsoft.web/serverfarms", "CIS-AZ-85")
def check_not_shared_tier(asset: Asset) -> EvalResult:
    """CIS-AZ-85: App Service Plan should not use Free/Shared compute tier in production."""
    props = asset.raw_properties or {}
    compute_mode = (props.get("computeMode") or "").lower()
    is_shared = compute_mode in _SHARED_COMPUTE_MODES
    return EvalResult(
        status="fail" if is_shared else "pass",
        evidence={"computeMode": props.get("computeMode")},
        description=(
            f"App Service Plan uses shared compute mode '{props.get('computeMode')}' — "
            "Free/Shared tiers have limited features and no SLA"
        )
        if is_shared
        else f"App Service Plan uses dedicated compute mode '{props.get('computeMode')}'",
    )


@check("microsoft.web/serverfarms", "CIS-AZ-86")
def check_zone_redundant(asset: Asset) -> EvalResult:
    """CIS-AZ-86: App Service Plan should have zone redundancy enabled for HA."""
    props = asset.raw_properties or {}
    zone_redundant = bool(props.get("zoneRedundant", False))
    return EvalResult(
        status="pass" if zone_redundant else "fail",
        evidence={"zoneRedundant": zone_redundant},
        description="Zone redundancy is enabled"
        if zone_redundant
        else "Zone redundancy is NOT enabled — app plan is vulnerable to a single zone failure",
    )


@check("microsoft.web/serverfarms", "CIS-AZ-87")
def check_multiple_workers(asset: Asset) -> EvalResult:
    """CIS-AZ-87: App Service Plan should have more than one worker for HA."""
    props = asset.raw_properties or {}
    workers = props.get("numberOfWorkers") or props.get("currentNumberOfWorkers") or 0
    try:
        workers = int(workers)
    except (TypeError, ValueError):
        workers = 0
    ok = workers >= 2
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"numberOfWorkers": workers},
        description=f"App Service Plan has {workers} workers"
        if ok
        else f"App Service Plan has only {workers} worker(s) — no high availability",
    )


@check("microsoft.web/serverfarms", "CIS-AZ-88")
def check_per_site_scaling(asset: Asset) -> EvalResult:
    """CIS-AZ-88: App Service Plan should enable per-site scaling when hosting multiple sites."""
    props = asset.raw_properties or {}
    per_site = bool(props.get("perSiteScaling", False))
    number_of_sites = props.get("numberOfSites") or 0
    try:
        number_of_sites = int(number_of_sites)
    except (TypeError, ValueError):
        number_of_sites = 0
    # Only flag as fail when plan hosts multiple sites without per-site scaling.
    if number_of_sites <= 1:
        return EvalResult(
            status="pass",
            evidence={"perSiteScaling": per_site, "numberOfSites": number_of_sites},
            description="Single-site plan — per-site scaling not required",
        )
    return EvalResult(
        status="pass" if per_site else "fail",
        evidence={"perSiteScaling": per_site, "numberOfSites": number_of_sites},
        description=f"Per-site scaling enabled on plan hosting {number_of_sites} sites"
        if per_site
        else (
            f"Per-site scaling NOT enabled on plan hosting {number_of_sites} sites — "
            "all sites scale together, preventing independent resource tuning"
        ),
    )
