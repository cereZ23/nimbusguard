"""Container Registry checks (CIS-AZ-39, 40)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.containerregistry/registries", "CIS-AZ-39")
def check_admin_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-39: Container registry admin user should be disabled."""
    props = asset.raw_properties or {}
    admin_enabled = props.get("adminUserEnabled", False)
    return EvalResult(
        status="pass" if not admin_enabled else "fail",
        evidence={"adminUserEnabled": admin_enabled},
        description="Admin user is disabled"
        if not admin_enabled
        else "Admin user is ENABLED — disable and use Azure AD / service principal instead",
    )


@check("microsoft.containerregistry/registries", "CIS-AZ-40")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AZ-40: Container registry should disable public network access."""
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
