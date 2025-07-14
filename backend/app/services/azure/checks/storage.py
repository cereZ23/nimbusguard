"""Storage account checks (CIS-AZ-04, 07, 09, 11, 12, 15, 72, 73, 74, 75)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.storage/storageaccounts", "CIS-AZ-09")
def check_https_only(asset: Asset) -> EvalResult:
    """CIS-AZ-09: Secure transfer (HTTPS) should be required."""
    props = asset.raw_properties or {}
    https_only = props.get("supportsHttpsTrafficOnly", False)
    return EvalResult(
        status="pass" if https_only else "fail",
        evidence={"supportsHttpsTrafficOnly": https_only},
        description="HTTPS-only access is enforced"
        if https_only
        else "HTTPS-only access is NOT enforced — data in transit may be intercepted",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-11")
def check_public_access_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-11: Public access should be disabled on storage accounts."""
    props = asset.raw_properties or {}
    public_access = props.get("allowBlobPublicAccess", True)
    return EvalResult(
        status="pass" if not public_access else "fail",
        evidence={"allowBlobPublicAccess": public_access},
        description="Public blob access is disabled"
        if not public_access
        else "Public blob access is enabled — anonymous read access possible",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-12")
def check_no_public_containers(asset: Asset) -> EvalResult:
    """CIS-AZ-12: Storage blob containers should not allow anonymous public access."""
    props = asset.raw_properties or {}
    public_access = props.get("allowBlobPublicAccess", True)
    return EvalResult(
        status="pass" if not public_access else "fail",
        evidence={"allowBlobPublicAccess": public_access},
        description="Container-level public access is blocked at account level"
        if not public_access
        else "Container-level public access is possible (account allows blob public access)",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-15")
def check_network_access_restricted(asset: Asset) -> EvalResult:
    """CIS-AZ-15: Storage accounts should restrict network access."""
    props = asset.raw_properties or {}
    network_acls = props.get("networkAcls", {})
    default_action = network_acls.get("defaultAction", "Allow")
    is_restricted = default_action.lower() == "deny"
    return EvalResult(
        status="pass" if is_restricted else "fail",
        evidence={
            "networkAcls.defaultAction": default_action,
        },
        description="Network access is restricted (default action: Deny)"
        if is_restricted
        else f"Network access is unrestricted (default action: {default_action})",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-07")
def check_cmk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-07: Storage accounts should use customer-managed keys."""
    props = asset.raw_properties or {}
    encryption = props.get("encryption", {})
    key_source = encryption.get("keySource", "Microsoft.Storage")
    uses_cmk = key_source != "Microsoft.Storage"
    return EvalResult(
        status="pass" if uses_cmk else "fail",
        evidence={"encryption.keySource": key_source},
        description="Storage uses customer-managed keys (CMK)"
        if uses_cmk
        else f"Storage uses platform-managed keys ({key_source}) — consider CMK for enhanced control",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-04")
def check_diagnostic_logs(asset: Asset) -> EvalResult:
    """CIS-AZ-04: Diagnostic logs should be enabled.

    Best-effort: Resource Graph doesn't always expose diagnostic settings.
    We check if the property exists; if not, we flag as unknown.
    """
    props = asset.raw_properties or {}
    diag = props.get("diagnosticSettings")
    if diag is not None:
        return EvalResult(
            status="pass",
            evidence={"diagnosticSettings": "present"},
            description="Diagnostic settings detected in raw properties",
        )
    return EvalResult(
        status="fail",
        evidence={"diagnosticSettings": "not_found_in_resource_graph"},
        description="Diagnostic settings not found in Resource Graph properties "
        "(may require separate API call to verify — best-effort check)",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-72")
def check_min_tls_version(asset: Asset) -> EvalResult:
    """CIS-AZ-72: Storage account should require minimum TLS 1.2."""
    props = asset.raw_properties or {}
    tls_version = props.get("minimumTlsVersion", "")
    is_ok = str(tls_version) >= "TLS1_2" if tls_version else False
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"minimumTlsVersion": tls_version},
        description="Minimum TLS version is TLS1_2 or higher"
        if is_ok
        else f"Minimum TLS version is '{tls_version or 'not set'}' — should be at least TLS1_2",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-73")
def check_infrastructure_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-73: Storage should have infrastructure encryption enabled."""
    props = asset.raw_properties or {}
    encryption = props.get("encryption", {})
    infra_enc = encryption.get("requireInfrastructureEncryption", False) if isinstance(encryption, dict) else False
    return EvalResult(
        status="pass" if infra_enc else "fail",
        evidence={"encryption.requireInfrastructureEncryption": infra_enc},
        description="Infrastructure encryption (double encryption) is enabled"
        if infra_enc
        else "Infrastructure encryption is NOT enabled — consider enabling for defense in depth",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-74")
def check_shared_key_access_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-74: Storage should disable shared key access."""
    props = asset.raw_properties or {}
    allow_shared = props.get("allowSharedKeyAccess", True)
    return EvalResult(
        status="pass" if not allow_shared else "fail",
        evidence={"allowSharedKeyAccess": allow_shared},
        description="Shared key access is disabled (Azure AD auth enforced)"
        if not allow_shared
        else "Shared key access is allowed — consider disabling in favor of Azure AD auth",
    )


@check("microsoft.storage/storageaccounts", "CIS-AZ-75")
def check_blob_versioning(asset: Asset) -> EvalResult:
    """CIS-AZ-75: Storage should have blob versioning enabled."""
    props = asset.raw_properties or {}
    versioning = props.get("isBlobVersioningEnabled", False)
    # Alternative path in blob service properties
    if not versioning:
        blob_props = props.get("blobServiceProperties", {})
        versioning = blob_props.get("isVersioningEnabled", False) if isinstance(blob_props, dict) else False
    return EvalResult(
        status="pass" if versioning else "fail",
        evidence={"isBlobVersioningEnabled": versioning},
        description="Blob versioning is enabled"
        if versioning
        else "Blob versioning is NOT enabled — enable for data protection and recovery",
    )
