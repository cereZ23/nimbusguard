"""Unit tests for M365 identity checks (microsoft365/tenant, CIS M365 §1 + §5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.m365.checks.identity import (
    _RESTRICTED_GUEST_ROLE_ID,
    check_admin_mfa_registration,
    check_global_admin_count,
    check_guest_invites_restricted,
    check_guest_role_restricted,
    check_legacy_auth_blocked,
    check_mfa_for_admins,
    check_mfa_for_all_users,
    check_no_disabled_privileged_accounts,
    check_passwords_never_expire,
    check_security_defaults_or_ca,
    check_user_consent_restricted,
    check_user_mfa_registration,
    check_users_cannot_create_security_groups,
    check_users_cannot_create_tenants,
    check_users_cannot_register_apps,
    check_weak_auth_methods_disabled,
)


def _asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/m365/{uuid.uuid4()}/tenant",
        resource_type="microsoft365/tenant",
        name="M365 Tenant",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _ca_policy(
    name="Policy", state="enabled", include_users=None, include_roles=None, controls=("mfa",), client_apps=None
):
    return {
        "displayName": name,
        "state": state,
        "conditions": {
            "users": {"includeUsers": include_users or [], "includeRoles": include_roles or []},
            "clientAppTypes": client_apps or [],
        },
        "grantControls": {"builtInControls": list(controls)},
    }


# ── Skip semantics (data not collected) ─────────────────────────────


def test_checks_skip_when_not_collected():
    asset = _asset({})
    assert check_global_admin_count(asset) is None
    assert check_mfa_for_admins(asset) is None
    assert check_users_cannot_register_apps(asset) is None
    assert check_passwords_never_expire(asset) is None
    assert check_weak_auth_methods_disabled(asset) is None


# ── §1 admin roles ──────────────────────────────────────────────────


def test_global_admin_count_pass():
    asset = _asset({"directory_roles": [{"displayName": "Global Administrator", "member_count": 3, "members": []}]})
    assert check_global_admin_count(asset).status == "pass"


def test_global_admin_count_fail_too_few():
    asset = _asset({"directory_roles": [{"displayName": "Global Administrator", "member_count": 1, "members": []}]})
    result = check_global_admin_count(asset)
    assert result.status == "fail"
    assert result.evidence["global_admin_count"] == 1


def test_global_admin_count_fail_too_many():
    asset = _asset({"directory_roles": [{"displayName": "Global Administrator", "member_count": 9, "members": []}]})
    assert check_global_admin_count(asset).status == "fail"


def test_disabled_privileged_accounts_fail():
    asset = _asset(
        {
            "directory_roles": [
                {
                    "displayName": "Global Administrator",
                    "member_count": 2,
                    "members": [
                        {"userPrincipalName": "ok@x", "accountEnabled": True},
                        {"userPrincipalName": "stale@x", "accountEnabled": False},
                    ],
                }
            ]
        }
    )
    result = check_no_disabled_privileged_accounts(asset)
    assert result.status == "fail"
    assert result.evidence["disabled_privileged_accounts"][0]["user"] == "stale@x"


def test_disabled_privileged_accounts_pass():
    asset = _asset(
        {
            "directory_roles": [
                {
                    "displayName": "Global Administrator",
                    "member_count": 1,
                    "members": [{"userPrincipalName": "ok@x", "accountEnabled": True}],
                }
            ]
        }
    )
    assert check_no_disabled_privileged_accounts(asset).status == "pass"


# ── §5 Conditional Access / security defaults ───────────────────────


def test_security_defaults_or_ca_pass_via_defaults():
    asset = _asset({"security_defaults": {"isEnabled": True}, "conditional_access_policies": []})
    assert check_security_defaults_or_ca(asset).status == "pass"


def test_security_defaults_or_ca_fail_when_nothing():
    asset = _asset({"security_defaults": {"isEnabled": False}, "conditional_access_policies": []})
    assert check_security_defaults_or_ca(asset).status == "fail"


def test_mfa_for_admins_pass_via_role_policy():
    asset = _asset(
        {
            "security_defaults": {"isEnabled": False},
            "conditional_access_policies": [_ca_policy(include_roles=["62e90394"])],
        }
    )
    assert check_mfa_for_admins(asset).status == "pass"


def test_mfa_for_admins_fail_disabled_policy():
    asset = _asset(
        {
            "security_defaults": {"isEnabled": False},
            "conditional_access_policies": [_ca_policy(state="disabled", include_roles=["62e90394"])],
        }
    )
    assert check_mfa_for_admins(asset).status == "fail"


def test_mfa_for_all_users_pass():
    asset = _asset(
        {
            "security_defaults": {"isEnabled": False},
            "conditional_access_policies": [_ca_policy(include_users=["All"])],
        }
    )
    assert check_mfa_for_all_users(asset).status == "pass"


def test_mfa_for_all_users_fail_role_scoped_only():
    asset = _asset(
        {
            "security_defaults": {"isEnabled": False},
            "conditional_access_policies": [_ca_policy(include_roles=["62e90394"])],
        }
    )
    assert check_mfa_for_all_users(asset).status == "fail"


def test_legacy_auth_blocked_pass():
    asset = _asset(
        {
            "security_defaults": {"isEnabled": False},
            "conditional_access_policies": [
                _ca_policy(controls=("block",), include_users=["All"], client_apps=["exchangeActiveSync", "other"])
            ],
        }
    )
    assert check_legacy_auth_blocked(asset).status == "pass"


def test_legacy_auth_blocked_fail():
    asset = _asset(
        {
            "security_defaults": {"isEnabled": False},
            "conditional_access_policies": [_ca_policy(include_users=["All"])],
        }
    )
    assert check_legacy_auth_blocked(asset).status == "fail"


# ── §5 MFA registration ─────────────────────────────────────────────


def test_admin_mfa_registration():
    ok = _asset({"mfa_registration": {"admin_total": 3, "admin_mfa_not_registered": 0}})
    bad = _asset({"mfa_registration": {"admin_total": 3, "admin_mfa_not_registered": 2}})
    assert check_admin_mfa_registration(ok).status == "pass"
    assert check_admin_mfa_registration(bad).status == "fail"


def test_user_mfa_registration_threshold():
    ok = _asset({"mfa_registration": {"mfa_coverage_pct": 97.5, "mfa_not_registered": 3}})
    bad = _asset({"mfa_registration": {"mfa_coverage_pct": 60.0, "mfa_not_registered": 40}})
    assert check_user_mfa_registration(ok).status == "pass"
    assert check_user_mfa_registration(bad).status == "fail"


# ── §5 authorization policy defaults ────────────────────────────────


def test_user_default_permissions():
    locked = _asset(
        {
            "authorization_policy": {
                "defaultUserRolePermissions": {
                    "allowedToCreateApps": False,
                    "allowedToCreateTenants": False,
                    "allowedToCreateSecurityGroups": False,
                    "permissionGrantPoliciesAssigned": [],
                }
            }
        }
    )
    open_tenant = _asset(
        {
            "authorization_policy": {
                "defaultUserRolePermissions": {
                    "allowedToCreateApps": True,
                    "allowedToCreateTenants": True,
                    "allowedToCreateSecurityGroups": True,
                    "permissionGrantPoliciesAssigned": ["ManagePermissionGrantsForSelf.microsoft-user-default-legacy"],
                }
            }
        }
    )
    assert check_users_cannot_register_apps(locked).status == "pass"
    assert check_users_cannot_register_apps(open_tenant).status == "fail"
    assert check_users_cannot_create_tenants(locked).status == "pass"
    assert check_users_cannot_create_tenants(open_tenant).status == "fail"
    assert check_users_cannot_create_security_groups(locked).status == "pass"
    assert check_users_cannot_create_security_groups(open_tenant).status == "fail"
    assert check_user_consent_restricted(locked).status == "pass"
    assert check_user_consent_restricted(open_tenant).status == "fail"


def test_user_consent_low_impact_passes():
    asset = _asset(
        {
            "authorization_policy": {
                "defaultUserRolePermissions": {
                    "permissionGrantPoliciesAssigned": ["ManagePermissionGrantsForSelf.microsoft-user-default-low"]
                }
            }
        }
    )
    assert check_user_consent_restricted(asset).status == "pass"


def test_guest_settings():
    restricted = _asset(
        {
            "authorization_policy": {
                "allowInvitesFrom": "adminsAndGuestInviters",
                "guestUserRoleId": _RESTRICTED_GUEST_ROLE_ID,
            }
        }
    )
    permissive = _asset(
        {
            "authorization_policy": {
                "allowInvitesFrom": "everyone",
                "guestUserRoleId": "10dae51f-b6af-4016-8d66-8c2a99b929b3",
            }
        }
    )
    assert check_guest_invites_restricted(restricted).status == "pass"
    assert check_guest_invites_restricted(permissive).status == "fail"
    assert check_guest_role_restricted(restricted).status == "pass"
    assert check_guest_role_restricted(permissive).status == "fail"


# ── §5 passwords + auth methods ─────────────────────────────────────


def test_passwords_never_expire():
    ok = _asset({"domains": [{"id": "contoso.com", "isVerified": True, "passwordValidityPeriodInDays": 2147483647}]})
    bad = _asset({"domains": [{"id": "contoso.com", "isVerified": True, "passwordValidityPeriodInDays": 90}]})
    assert check_passwords_never_expire(ok).status == "pass"
    result = check_passwords_never_expire(bad)
    assert result.status == "fail"
    assert result.evidence["domains_with_expiration"] == ["contoso.com"]


def test_weak_auth_methods():
    ok = _asset(
        {
            "auth_methods_policy": {
                "authenticationMethodConfigurations": [
                    {"id": "Sms", "state": "disabled"},
                    {"id": "Voice", "state": "disabled"},
                    {"id": "MicrosoftAuthenticator", "state": "enabled"},
                ]
            }
        }
    )
    bad = _asset({"auth_methods_policy": {"authenticationMethodConfigurations": [{"id": "Sms", "state": "enabled"}]}})
    assert check_weak_auth_methods_disabled(ok).status == "pass"
    result = check_weak_auth_methods_disabled(bad)
    assert result.status == "fail"
    assert result.evidence["weak_methods_enabled"] == ["Sms"]
