"""Unit tests for M365 SharePoint/OneDrive and Teams checks (CIS M365 §7 + §8)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.m365.checks.sharepoint import (
    check_external_sharing_restricted,
    check_guests_must_match_invited_account,
    check_idle_session_signout,
    check_legacy_auth_disabled,
    check_resharing_by_guests_disabled,
    check_sharing_domain_restriction,
    check_unmanaged_sync_restricted,
)
from app.services.m365.checks.teams import check_rsc_consent_restricted


def _spo_asset(settings: dict | None) -> Asset:
    raw = {"settings": settings} if settings is not None else {}
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/m365/{uuid.uuid4()}/sharepoint",
        resource_type="microsoft365/sharepoint",
        name="SharePoint & OneDrive",
        region="global",
        raw_properties=raw,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _teams_asset(settings: dict | None) -> Asset:
    raw = {"teams_app_settings": settings} if settings is not None else {}
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/m365/{uuid.uuid4()}/teams",
        resource_type="microsoft365/teams",
        name="Microsoft Teams",
        region="global",
        raw_properties=raw,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


# ── Skip semantics ──────────────────────────────────────────────────


def test_sharepoint_checks_skip_when_not_collected():
    asset = _spo_asset(None)
    assert check_legacy_auth_disabled(asset) is None
    assert check_external_sharing_restricted(asset) is None
    assert check_idle_session_signout(asset) is None


def test_teams_check_skips_when_not_collected():
    assert check_rsc_consent_restricted(_teams_asset(None)) is None


# ── §7 SharePoint ───────────────────────────────────────────────────


def test_legacy_auth():
    assert check_legacy_auth_disabled(_spo_asset({"isLegacyAuthProtocolsEnabled": False})).status == "pass"
    assert check_legacy_auth_disabled(_spo_asset({"isLegacyAuthProtocolsEnabled": True})).status == "fail"


def test_external_sharing_capability():
    assert (
        check_external_sharing_restricted(_spo_asset({"sharingCapability": "existingExternalUserSharingOnly"})).status
        == "pass"
    )
    assert check_external_sharing_restricted(_spo_asset({"sharingCapability": "disabled"})).status == "pass"
    assert (
        check_external_sharing_restricted(_spo_asset({"sharingCapability": "externalUserAndGuestSharing"})).status
        == "fail"
    )


def test_guests_must_match_invited_account():
    ok = _spo_asset({"isRequireAcceptingUserToMatchInvitedUserEnabled": True})
    bad = _spo_asset({"isRequireAcceptingUserToMatchInvitedUserEnabled": False})
    assert check_guests_must_match_invited_account(ok).status == "pass"
    assert check_guests_must_match_invited_account(bad).status == "fail"


def test_sharing_domain_restriction():
    allow = _spo_asset(
        {
            "sharingCapability": "externalUserSharingOnly",
            "sharingDomainRestrictionMode": "allowList",
            "sharingAllowedDomainList": ["partner.com"],
        }
    )
    none_mode = _spo_asset({"sharingCapability": "externalUserSharingOnly", "sharingDomainRestrictionMode": "none"})
    disabled = _spo_asset({"sharingCapability": "disabled"})
    assert check_sharing_domain_restriction(allow).status == "pass"
    assert check_sharing_domain_restriction(none_mode).status == "fail"
    assert check_sharing_domain_restriction(disabled).status == "pass"


def test_resharing_by_guests():
    assert check_resharing_by_guests_disabled(_spo_asset({"isResharingByExternalUsersEnabled": False})).status == "pass"
    assert check_resharing_by_guests_disabled(_spo_asset({"isResharingByExternalUsersEnabled": True})).status == "fail"


def test_unmanaged_sync():
    assert check_unmanaged_sync_restricted(_spo_asset({"isUnmanagedSyncAppForTenantRestricted": True})).status == "pass"
    assert (
        check_unmanaged_sync_restricted(_spo_asset({"isUnmanagedSyncAppForTenantRestricted": False})).status == "fail"
    )


def test_idle_session_signout():
    ok = _spo_asset({"idleSessionSignOut": {"isEnabled": True, "signOutAfterInSeconds": 3600}})
    bad = _spo_asset({"idleSessionSignOut": {"isEnabled": False}})
    assert check_idle_session_signout(ok).status == "pass"
    assert check_idle_session_signout(bad).status == "fail"


def test_idle_session_signout_settings_present_but_unconfigured():
    # settings collected but idleSessionSignOut absent -> fail (not configured)
    asset = _spo_asset({"sharingCapability": "disabled"})
    assert check_idle_session_signout(asset).status == "fail"


# ── §8 Teams ────────────────────────────────────────────────────────


def test_teams_rsc_consent():
    ok = _teams_asset(
        {
            "isChatResourceSpecificConsentEnabled": False,
            "isUserPersonalScopeResourceSpecificConsentEnabled": False,
        }
    )
    bad = _teams_asset(
        {
            "isChatResourceSpecificConsentEnabled": True,
            "isUserPersonalScopeResourceSpecificConsentEnabled": False,
        }
    )
    assert check_rsc_consent_restricted(ok).status == "pass"
    assert check_rsc_consent_restricted(bad).status == "fail"
