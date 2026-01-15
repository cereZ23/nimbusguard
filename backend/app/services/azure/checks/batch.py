"""Batch Account checks (CIS-AZ-79, 80)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.batch/batchaccounts", "CIS-AZ-79")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AZ-79: Batch account should disable public network access."""
    props = asset.raw_properties or {}
    public_access = props.get("publicNetworkAccess", "Enabled")
    is_disabled = str(public_access).lower() == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccess": public_access},
        description="Public network access is disabled"
        if is_disabled
        else f"Public network access is '{public_access}' — restrict via private endpoints",
    )


@check("microsoft.batch/batchaccounts", "CIS-AZ-80")
def check_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-80: Batch account should use CMK encryption."""
    props = asset.raw_properties or {}
    encryption = props.get("encryption", {})
    key_source = encryption.get("keySource", "") if isinstance(encryption, dict) else ""
    uses_cmk = str(key_source).lower() in ("microsoft.keyvault", "keyvault")
    return EvalResult(
        status="pass" if uses_cmk else "fail",
        evidence={"encryption.keySource": key_source or None},
        description="Batch account uses customer-managed key encryption"
        if uses_cmk
        else "Batch account does NOT use CMK — consider customer-managed keys",
    )
