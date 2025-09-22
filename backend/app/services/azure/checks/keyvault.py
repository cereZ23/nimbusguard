"""Key Vault checks (CIS-AZ-16, 17, 18, 21, 22, 76, 77, 78)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.keyvault/vaults", "CIS-AZ-16")
def check_purge_protection(asset: Asset) -> EvalResult:
    """CIS-AZ-16: Key vaults should have purge protection enabled."""
    props = asset.raw_properties or {}
    enabled = props.get("enablePurgeProtection", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"enablePurgeProtection": enabled},
        description="Purge protection is enabled"
        if enabled
        else "Purge protection is NOT enabled — deleted keys/secrets can be permanently lost",
    )


@check("microsoft.keyvault/vaults", "CIS-AZ-17")
def check_soft_delete(asset: Asset) -> EvalResult:
    """CIS-AZ-17: Key vaults should have soft delete enabled."""
    props = asset.raw_properties or {}
    enabled = props.get("enableSoftDelete", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"enableSoftDelete": enabled},
        description="Soft delete is enabled"
        if enabled
        else "Soft delete is NOT enabled — deleted keys/secrets cannot be recovered",
    )


@check("microsoft.keyvault/vaults/keys", "CIS-AZ-18")
def check_key_expiration(asset: Asset) -> EvalResult:
    """CIS-AZ-18: Keys should have an expiration date set."""
    props = asset.raw_properties or {}
    attributes = props.get("attributes", {})
    expires = attributes.get("expires") or attributes.get("exp")
    return EvalResult(
        status="pass" if expires is not None else "fail",
        evidence={"attributes.expires": expires},
        description="Key has an expiration date set"
        if expires is not None
        else "Key does NOT have an expiration date — keys should be rotated periodically",
    )


@check("microsoft.keyvault/vaults", "CIS-AZ-21")
def check_network_acl(asset: Asset) -> EvalResult:
    """CIS-AZ-21: Key Vault should restrict network access."""
    props = asset.raw_properties or {}
    network_acls = props.get("networkAcls", {})
    default_action = network_acls.get("defaultAction", "Allow")
    is_restricted = default_action.lower() == "deny"
    return EvalResult(
        status="pass" if is_restricted else "fail",
        evidence={"networkAcls.defaultAction": default_action},
        description="Key Vault network access is restricted (default: Deny)"
        if is_restricted
        else f"Key Vault network access is unrestricted (default: {default_action})",
    )


@check("microsoft.keyvault/vaults", "CIS-AZ-22")
def check_rbac_authorization(asset: Asset) -> EvalResult:
    """CIS-AZ-22: Key Vault should use RBAC authorization."""
    props = asset.raw_properties or {}
    enabled = props.get("enableRbacAuthorization", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"enableRbacAuthorization": enabled},
        description="RBAC authorization is enabled"
        if enabled
        else "RBAC authorization is NOT enabled — consider migrating from access policies to RBAC",
    )


@check("microsoft.keyvault/vaults/secrets", "CIS-AZ-76")
def check_secret_expiration(asset: Asset) -> EvalResult:
    """CIS-AZ-76: Key Vault secrets should have an expiration date set."""
    props = asset.raw_properties or {}
    attributes = props.get("attributes", {})
    expires = attributes.get("expires") or attributes.get("exp")
    return EvalResult(
        status="pass" if expires is not None else "fail",
        evidence={"attributes.expires": expires},
        description="Secret has an expiration date set"
        if expires is not None
        else "Secret does NOT have an expiration date — secrets should be rotated periodically",
    )


@check("microsoft.keyvault/vaults/certificates", "CIS-AZ-77")
def check_certificate_expiration(asset: Asset) -> EvalResult:
    """CIS-AZ-77: Key Vault certificates should have an expiration date set."""
    props = asset.raw_properties or {}
    attributes = props.get("attributes", {})
    expires = attributes.get("expires") or attributes.get("exp")
    return EvalResult(
        status="pass" if expires is not None else "fail",
        evidence={"attributes.expires": expires},
        description="Certificate has an expiration date set"
        if expires is not None
        else "Certificate does NOT have an expiration date — ensure certificates are renewed",
    )


@check("microsoft.keyvault/vaults", "CIS-AZ-78")
def check_private_endpoint(asset: Asset) -> EvalResult:
    """CIS-AZ-78: Key Vault should use private endpoints."""
    props = asset.raw_properties or {}
    private_endpoints = props.get("privateEndpointConnections", [])
    has_pe = isinstance(private_endpoints, list) and len(private_endpoints) > 0
    return EvalResult(
        status="pass" if has_pe else "fail",
        evidence={"privateEndpointConnections": len(private_endpoints) if isinstance(private_endpoints, list) else 0},
        description="Key Vault has private endpoint connections configured"
        if has_pe
        else "No private endpoints configured — access goes through public network",
    )
