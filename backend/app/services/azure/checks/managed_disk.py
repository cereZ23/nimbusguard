"""Managed Disk checks (CIS-AZ-63, 64)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.compute/disks", "CIS-AZ-63")
def check_disk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-63: Managed disks should be encrypted."""
    props = asset.raw_properties or {}
    encryption = props.get("encryption", {})
    enc_type = encryption.get("type", "") if isinstance(encryption, dict) else ""
    # EncryptionAtRestWithPlatformKey is the default (acceptable)
    # EncryptionAtRestWithCustomerKey or EncryptionAtRestWithPlatformAndCustomerKeys are better
    has_encryption = enc_type != "" and enc_type is not None
    return EvalResult(
        status="pass" if has_encryption else "fail",
        evidence={"encryption.type": enc_type or None},
        description=f"Disk encryption type: {enc_type}"
        if has_encryption
        else "Disk encryption type is not set — ensure encryption is enabled",
    )


@check("microsoft.compute/disks", "CIS-AZ-64")
def check_network_access_policy(asset: Asset) -> EvalResult:
    """CIS-AZ-64: Managed disks should restrict network access."""
    props = asset.raw_properties or {}
    policy = props.get("networkAccessPolicy", "AllowAll")
    is_restricted = str(policy).lower() in ("denyall", "allowprivate")
    return EvalResult(
        status="pass" if is_restricted else "fail",
        evidence={"networkAccessPolicy": policy},
        description=f"Disk network access policy is '{policy}'"
        if is_restricted
        else f"Disk network access policy is '{policy}' — restrict to DenyAll or AllowPrivate",
    )
