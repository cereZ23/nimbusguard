"""SharePoint / OneDrive checks for the microsoft365/sharepoint asset (CIS M365 §7).

Evaluates the tenant admin settings collected from Graph
``GET /admin/sharepoint/settings`` (stored under raw_properties["settings"]).
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check
from app.services.m365.checks.common import prop

# sharingCapability values considered acceptably restrictive
_RESTRICTED_SHARING = {"externalUserSharingOnly", "existingExternalUserSharingOnly", "disabled"}


@check("microsoft365/sharepoint", "CIS-M365-7.2.1")
def check_legacy_auth_disabled(asset: Asset) -> EvalResult | None:
    """Legacy authentication protocols to SharePoint are disabled."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    enabled = settings.get("isLegacyAuthProtocolsEnabled", True)
    return EvalResult(
        status="pass" if not enabled else "fail",
        evidence={"isLegacyAuthProtocolsEnabled": enabled},
        description="Legacy authentication protocols are enabled for SharePoint"
        if enabled
        else "Legacy authentication protocols are disabled",
    )


@check("microsoft365/sharepoint", "CIS-M365-7.2.3")
def check_external_sharing_restricted(asset: Asset) -> EvalResult | None:
    """External sharing requires sign-in (no 'anyone' links tenant-wide)."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    capability = settings.get("sharingCapability", "externalUserAndGuestSharing")
    ok = capability in _RESTRICTED_SHARING
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"sharingCapability": capability},
        description=f"Tenant sharing capability is '{capability}'",
    )


@check("microsoft365/sharepoint", "CIS-M365-7.2.5")
def check_guests_must_match_invited_account(asset: Asset) -> EvalResult | None:
    """Guests must accept invitations with the invited account."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    required = settings.get("isRequireAcceptingUserToMatchInvitedUserEnabled", False)
    return EvalResult(
        status="pass" if required else "fail",
        evidence={"isRequireAcceptingUserToMatchInvitedUserEnabled": required},
        description="Guests can accept sharing invitations with any account"
        if not required
        else "Guests must use the invited account",
    )


@check("microsoft365/sharepoint", "CIS-M365-7.2.6")
def check_sharing_domain_restriction(asset: Asset) -> EvalResult | None:
    """External sharing is restricted by domain allow/block list."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    capability = settings.get("sharingCapability", "externalUserAndGuestSharing")
    if capability == "disabled":
        return EvalResult(
            status="pass",
            evidence={"sharingCapability": capability},
            description="External sharing is disabled entirely",
        )
    mode = settings.get("sharingDomainRestrictionMode", "none")
    allow_list = settings.get("sharingAllowedDomainList") or []
    block_list = settings.get("sharingBlockedDomainList") or []
    ok = (mode == "allowList" and allow_list) or (mode == "blockList" and block_list)
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={
            "sharingDomainRestrictionMode": mode,
            "allowed_domains": len(allow_list),
            "blocked_domains": len(block_list),
        },
        description="External sharing has no domain restriction"
        if not ok
        else f"External sharing restricted via {mode}",
    )


@check("microsoft365/sharepoint", "CIS-M365-7.2.9")
def check_resharing_by_guests_disabled(asset: Asset) -> EvalResult | None:
    """External users cannot re-share content they don't own."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    enabled = settings.get("isResharingByExternalUsersEnabled", True)
    return EvalResult(
        status="pass" if not enabled else "fail",
        evidence={"isResharingByExternalUsersEnabled": enabled},
        description="External users can re-share content" if enabled else "Re-sharing by external users is disabled",
    )


@check("microsoft365/sharepoint", "CIS-M365-7.3.2")
def check_unmanaged_sync_restricted(asset: Asset) -> EvalResult | None:
    """OneDrive sync is restricted to managed devices."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    restricted = settings.get("isUnmanagedSyncAppForTenantRestricted", False)
    return EvalResult(
        status="pass" if restricted else "fail",
        evidence={"isUnmanagedSyncAppForTenantRestricted": restricted},
        description="Unmanaged devices can sync OneDrive content"
        if not restricted
        else "OneDrive sync is restricted to managed devices",
    )


@check("microsoft365/sharepoint", "CIS-M365-7.3.4")
def check_idle_session_signout(asset: Asset) -> EvalResult | None:
    """Idle browser sessions are signed out automatically."""
    settings = prop(asset, "settings")
    if settings is None:
        return None
    idle = settings.get("idleSessionSignOut") or {}
    enabled = idle.get("isEnabled", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"idleSessionSignOut": idle},
        description="Idle session sign-out is disabled" if not enabled else "Idle session sign-out is enabled",
    )
