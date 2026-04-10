"""Log Analytics workspace checks (CIS-AZ-61, 62, 100..103)."""

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


@check("microsoft.operationalinsights/workspaces", "CIS-AZ-100")
def check_daily_quota_configured(asset: Asset) -> EvalResult:
    """CIS-AZ-100: Log Analytics workspace should have a daily ingestion quota to control costs."""
    props = asset.raw_properties or {}
    capping = props.get("workspaceCapping") or {}
    if not isinstance(capping, dict):
        capping = {}
    quota = capping.get("dailyQuotaGb")
    try:
        quota_val = float(quota) if quota is not None else -1.0
    except (TypeError, ValueError):
        quota_val = -1.0
    # Azure uses -1 as the sentinel for "no cap".
    is_set = quota_val > 0
    return EvalResult(
        status="pass" if is_set else "fail",
        evidence={"workspaceCapping.dailyQuotaGb": quota_val},
        description=f"Daily ingestion quota is set to {quota_val} GB"
        if is_set
        else "Daily ingestion quota is NOT set — log costs can grow unbounded",
    )


@check("microsoft.operationalinsights/workspaces", "CIS-AZ-101")
def check_public_access_query_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-101: Log Analytics workspace should disable public network access for queries."""
    props = asset.raw_properties or {}
    access = (props.get("publicNetworkAccessForQuery") or "").lower()
    is_disabled = access == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccessForQuery": props.get("publicNetworkAccessForQuery")},
        description="Public network access for query is disabled"
        if is_disabled
        else (
            f"Public network access for query is '{props.get('publicNetworkAccessForQuery')}' — "
            "logs are queryable from the public internet"
        ),
    )


@check("microsoft.operationalinsights/workspaces", "CIS-AZ-102")
def check_public_access_ingestion_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-102: Log Analytics workspace should disable public network access for ingestion."""
    props = asset.raw_properties or {}
    access = (props.get("publicNetworkAccessForIngestion") or "").lower()
    is_disabled = access == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccessForIngestion": props.get("publicNetworkAccessForIngestion")},
        description="Public network access for ingestion is disabled"
        if is_disabled
        else (
            f"Public network access for ingestion is '{props.get('publicNetworkAccessForIngestion')}' — "
            "workspace accepts logs from the public internet"
        ),
    )


@check("microsoft.operationalinsights/workspaces", "CIS-AZ-103")
def check_resource_permissions_only(asset: Asset) -> EvalResult:
    """CIS-AZ-103: Log Analytics workspace should use resource-level permissions (RBAC)."""
    props = asset.raw_properties or {}
    features = props.get("features") or {}
    if not isinstance(features, dict):
        features = {}
    rbac_only = bool(features.get("enableLogAccessUsingOnlyResourcePermissions", False))
    return EvalResult(
        status="pass" if rbac_only else "fail",
        evidence={"features.enableLogAccessUsingOnlyResourcePermissions": rbac_only},
        description="Workspace access is restricted to resource-level permissions (RBAC)"
        if rbac_only
        else (
            "Workspace access is NOT restricted to resource-level permissions — "
            "users with workspace-level access see all logs regardless of resource RBAC"
        ),
    )
