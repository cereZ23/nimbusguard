"""Cosmos DB checks (CIS-AZ-35, 36, 81, 82)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-35")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AZ-35: Cosmos DB should disable public network access."""
    props = asset.raw_properties or {}
    public_access = props.get("publicNetworkAccess", "Enabled")
    is_disabled = str(public_access).lower() == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccess": public_access},
        description="Public network access is disabled"
        if is_disabled
        else f"Public network access is '{public_access}' — should be disabled",
    )


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-36")
def check_vnet_filter(asset: Asset) -> EvalResult:
    """CIS-AZ-36: Cosmos DB should enable virtual network filter."""
    props = asset.raw_properties or {}
    vnet_filter = props.get("isVirtualNetworkFilterEnabled", False)
    return EvalResult(
        status="pass" if vnet_filter else "fail",
        evidence={"isVirtualNetworkFilterEnabled": vnet_filter},
        description="Virtual network filter is enabled"
        if vnet_filter
        else "Virtual network filter is NOT enabled — restrict access via VNet rules",
    )


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-81")
def check_cmk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-81: Cosmos DB should use customer-managed key encryption."""
    props = asset.raw_properties or {}
    key_vault_uri = props.get("keyVaultKeyUri")
    has_cmk = key_vault_uri is not None
    return EvalResult(
        status="pass" if has_cmk else "fail",
        evidence={"keyVaultKeyUri": "configured" if has_cmk else None},
        description="Cosmos DB uses customer-managed key encryption"
        if has_cmk
        else "Cosmos DB uses service-managed keys — consider CMK for enhanced control",
    )


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-82")
def check_automatic_failover(asset: Asset) -> EvalResult:
    """CIS-AZ-82: Cosmos DB should have automatic failover enabled."""
    props = asset.raw_properties or {}
    failover = props.get("enableAutomaticFailover", False)
    return EvalResult(
        status="pass" if failover else "fail",
        evidence={"enableAutomaticFailover": failover},
        description="Automatic failover is enabled"
        if failover
        else "Automatic failover is NOT enabled — enable for high availability",
    )
