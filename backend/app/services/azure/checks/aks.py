"""AKS (Managed Kubernetes) checks (CIS-AZ-41, 42, 83, 84)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.containerservice/managedclusters", "CIS-AZ-41")
def check_rbac_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-41: AKS clusters should have RBAC enabled."""
    props = asset.raw_properties or {}
    rbac = props.get("enableRBAC", False)
    return EvalResult(
        status="pass" if rbac else "fail",
        evidence={"enableRBAC": rbac},
        description="Kubernetes RBAC is enabled"
        if rbac
        else "Kubernetes RBAC is NOT enabled — enable for proper access control",
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-42")
def check_network_policy(asset: Asset) -> EvalResult:
    """CIS-AZ-42: AKS clusters should have a network policy configured."""
    props = asset.raw_properties or {}
    network_profile = props.get("networkProfile", {})
    policy = network_profile.get("networkPolicy") if isinstance(network_profile, dict) else None
    has_policy = policy is not None and str(policy).lower() not in ("", "none")
    return EvalResult(
        status="pass" if has_policy else "fail",
        evidence={"networkProfile.networkPolicy": policy},
        description=f"Network policy is configured ({policy})"
        if has_policy
        else "No network policy configured — configure calico or azure network policy",
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-83")
def check_private_cluster(asset: Asset) -> EvalResult:
    """CIS-AZ-83: AKS cluster should be private."""
    props = asset.raw_properties or {}
    api_profile = props.get("apiServerAccessProfile", {})
    private = api_profile.get("enablePrivateCluster", False) if isinstance(api_profile, dict) else False
    return EvalResult(
        status="pass" if private else "fail",
        evidence={"apiServerAccessProfile.enablePrivateCluster": private},
        description="AKS cluster API server is private"
        if private
        else "AKS cluster API server is PUBLIC — enable private cluster for production",
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-84")
def check_aad_integration(asset: Asset) -> EvalResult:
    """CIS-AZ-84: AKS cluster should have Azure AD integration enabled."""
    props = asset.raw_properties or {}
    aad_profile = props.get("aadProfile")
    has_aad = aad_profile is not None and isinstance(aad_profile, dict)
    return EvalResult(
        status="pass" if has_aad else "fail",
        evidence={"aadProfile": "configured" if has_aad else None},
        description="Azure AD integration is enabled"
        if has_aad
        else "Azure AD integration is NOT configured — enable for centralized identity management",
    )
