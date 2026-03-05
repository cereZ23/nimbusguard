"""Log Analytics workspace checks (CIS-AZ-61, 62)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.operationalinsights/workspaces", "CIS-AZ-61")
def check_retention_days(asset: Asset) -> EvalResult:
    """CIS-AZ-61: Log Analytics workspace retention should be >= 90 days."""
    props = asset.raw_properties or {}
    retention = props.get("retentionInDays", 0)
    try:
        days = int(retention)
    except (TypeError, ValueError):
        days = 0
    is_ok = days >= 90
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"retentionInDays": days},
        description=f"Log retention is {days} days (>= 90)"
        if is_ok
        else f"Log retention is {days} days — should be at least 90 days for compliance",
    )


@check("microsoft.operationalinsights/workspaces", "CIS-AZ-62")
def check_cmk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-62: Log Analytics workspace should use CMK encryption."""
    props = asset.raw_properties or {}
    # Check for cluster-based CMK
    cluster_id = props.get("clusterResourceId")
    # Check direct CMK config
    encryption = props.get("encryption", {})
    key_vault_props = encryption.get("keyVaultProperties") if isinstance(encryption, dict) else None
    has_cmk = cluster_id is not None or key_vault_props is not None
    return EvalResult(
        status="pass" if has_cmk else "fail",
        evidence={
            "clusterResourceId": cluster_id,
            "encryption.keyVaultProperties": "present" if key_vault_props else None,
        },
        description="Log Analytics workspace uses customer-managed key encryption"
        if has_cmk
        else "Log Analytics workspace does NOT use CMK — data encrypted with Microsoft-managed keys",
    )
