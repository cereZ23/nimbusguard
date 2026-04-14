"""AKS hardening checks (CIS-AZ-128..134).

Complements the baseline AKS checks in ``aks.py`` (RBAC, network policy,
private cluster, Azure AD integration) with deeper hardening controls that
map to the CIS Kubernetes Benchmark and modern AKS security best practices.

All checks read ``raw_properties`` collected by the generic Resource Graph
inventory query for ``microsoft.containerservice/managedclusters`` — no
new collector code or permissions.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# Auto-upgrade channels that represent an actively managed upgrade cadence.
# "none" / "None" means the cluster is pinned to a specific version and will
# never get security patches automatically, which is the fail case.
_MANAGED_UPGRADE_CHANNELS = {"patch", "stable", "rapid", "node-image"}


@check("microsoft.containerservice/managedclusters", "CIS-AZ-128")
def check_api_server_authorized_ip_ranges(asset: Asset) -> EvalResult:
    """CIS-AZ-128: AKS API server should have authorized IP ranges configured."""
    props = asset.raw_properties or {}
    api_profile = props.get("apiServerAccessProfile") or {}
    if not isinstance(api_profile, dict):
        api_profile = {}

    # If the cluster is private, IP ranges are not required — the API server
    # is not reachable from the public internet at all.
    if api_profile.get("enablePrivateCluster"):
        return EvalResult(
            status="pass",
            evidence={"enablePrivateCluster": True},
            description="Cluster is private — authorized IP ranges not required",
        )

    authorized = api_profile.get("authorizedIPRanges") or []
    if not isinstance(authorized, list):
        authorized = []
    has_ranges = len(authorized) > 0
    return EvalResult(
        status="pass" if has_ranges else "fail",
        evidence={"authorizedIPRanges_count": len(authorized)},
        description=(
            f"API server restricts access to {len(authorized)} authorized IP range(s)"
            if has_ranges
            else (
                "AKS API server is reachable from the public internet without IP allow-list — "
                "configure apiServerAccessProfile.authorizedIPRanges or enable private cluster"
            )
        ),
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-129")
def check_aks_managed_identity(asset: Asset) -> EvalResult:
    """CIS-AZ-129: AKS cluster should use managed identity (not service principal)."""
    props = asset.raw_properties or {}
    identity = props.get("identity") or {}
    if not isinstance(identity, dict):
        identity = {}
    identity_type = (identity.get("type") or "").lower()
    has_managed_identity = identity_type in ("systemassigned", "userassigned", "systemassigned, userassigned")
    # If no identity block, the cluster is using a service principal — fail.
    return EvalResult(
        status="pass" if has_managed_identity else "fail",
        evidence={"identity.type": identity.get("type")},
        description=(
            f"Cluster uses managed identity ({identity.get('type')})"
            if has_managed_identity
            else (
                "Cluster uses a service principal — migrate to managed identity "
                "so that credentials are rotated automatically by Azure"
            )
        ),
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-130")
def check_azure_policy_addon(asset: Asset) -> EvalResult:
    """CIS-AZ-130: AKS cluster should have the Azure Policy add-on enabled."""
    props = asset.raw_properties or {}
    addons = props.get("addonProfiles") or {}
    if not isinstance(addons, dict):
        addons = {}
    # The Azure Policy add-on is registered under different keys depending on
    # the API version: "azurepolicy" (most common) and "policy" (legacy).
    candidates = ["azurepolicy", "azurePolicy", "policy"]
    enabled = False
    matched_key = None
    for key in candidates:
        addon = addons.get(key)
        if isinstance(addon, dict) and addon.get("enabled"):
            enabled = True
            matched_key = key
            break
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"addon_key": matched_key, "addons_available": list(addons.keys())},
        description=(
            f"Azure Policy add-on is enabled (key: {matched_key})"
            if enabled
            else (
                "Azure Policy add-on is NOT enabled — enable it so that Kubernetes "
                "workloads are evaluated against built-in and custom Azure Policy initiatives"
            )
        ),
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-131")
def check_workload_identity_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-131: AKS cluster should have Workload Identity and OIDC issuer enabled."""
    props = asset.raw_properties or {}
    security_profile = props.get("securityProfile") or {}
    if not isinstance(security_profile, dict):
        security_profile = {}
    wi = security_profile.get("workloadIdentity") or {}
    if not isinstance(wi, dict):
        wi = {}
    wi_enabled = bool(wi.get("enabled"))

    oidc = props.get("oidcIssuerProfile") or {}
    if not isinstance(oidc, dict):
        oidc = {}
    oidc_enabled = bool(oidc.get("enabled"))

    ok = wi_enabled and oidc_enabled
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={
            "workloadIdentity.enabled": wi_enabled,
            "oidcIssuerProfile.enabled": oidc_enabled,
        },
        description=(
            "Workload Identity and OIDC issuer are both enabled"
            if ok
            else (
                "Workload Identity requires both securityProfile.workloadIdentity.enabled "
                "and oidcIssuerProfile.enabled to be true — enable them to allow pods to "
                "authenticate to Azure using federated identity instead of static secrets"
            )
        ),
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-132")
def check_local_accounts_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-132: AKS cluster should have local admin accounts disabled."""
    props = asset.raw_properties or {}
    # When disableLocalAccounts is true, only Azure AD identities can access
    # the cluster via kubectl — no static certificates.
    disabled = bool(props.get("disableLocalAccounts", False))
    return EvalResult(
        status="pass" if disabled else "fail",
        evidence={"disableLocalAccounts": disabled},
        description=(
            "Local admin accounts are disabled — only Azure AD identities can access the cluster"
            if disabled
            else (
                "Local admin accounts are enabled — the cluster accepts kubectl access via "
                "static client certificates, bypassing Entra ID. Set disableLocalAccounts=true."
            )
        ),
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-133")
def check_azure_rbac_for_kubernetes(asset: Asset) -> EvalResult:
    """CIS-AZ-133: AKS cluster should use Azure RBAC for Kubernetes authorisation."""
    props = asset.raw_properties or {}
    aad_profile = props.get("aadProfile") or {}
    if not isinstance(aad_profile, dict):
        aad_profile = {}
    azure_rbac = bool(aad_profile.get("enableAzureRBAC"))
    return EvalResult(
        status="pass" if azure_rbac else "fail",
        evidence={"aadProfile.enableAzureRBAC": azure_rbac},
        description=(
            "Azure RBAC for Kubernetes is enabled — authorisation decisions go through Azure roles"
            if azure_rbac
            else (
                "Azure RBAC for Kubernetes is NOT enabled — the cluster still relies on "
                "native Kubernetes ClusterRoleBindings which bypass Azure audit. Enable "
                "aadProfile.enableAzureRBAC to consolidate authorisation in Entra ID."
            )
        ),
    )


@check("microsoft.containerservice/managedclusters", "CIS-AZ-134")
def check_auto_upgrade_channel(asset: Asset) -> EvalResult:
    """CIS-AZ-134: AKS cluster should have an auto-upgrade channel configured."""
    props = asset.raw_properties or {}
    auto_upgrade = props.get("autoUpgradeProfile") or {}
    if not isinstance(auto_upgrade, dict):
        auto_upgrade = {}
    channel = (auto_upgrade.get("upgradeChannel") or "").strip().lower()
    is_managed = channel in _MANAGED_UPGRADE_CHANNELS
    return EvalResult(
        status="pass" if is_managed else "fail",
        evidence={"autoUpgradeProfile.upgradeChannel": auto_upgrade.get("upgradeChannel")},
        description=(
            f"Auto-upgrade channel is '{auto_upgrade.get('upgradeChannel')}' — "
            "cluster will receive security patches automatically"
            if is_managed
            else (
                f"Auto-upgrade channel is '{auto_upgrade.get('upgradeChannel') or 'none'}' — "
                "cluster is pinned to a version and will not get security patches. "
                "Set upgradeChannel to 'patch' or 'stable' for production workloads."
            )
        ),
    )
