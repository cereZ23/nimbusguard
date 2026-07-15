"""Identity checks for the microsoft365/tenant asset (CIS M365 §1 + §5).

Evaluates Entra tenant-wide identity posture collected via Microsoft Graph:
Conditional Access, security defaults, authorization policy, directory
roles, MFA registration, domains, and authentication method policies.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check
from app.services.m365.checks.common import prop

# Entra "Restricted Guest User" role template — the most limited guest role.
_RESTRICTED_GUEST_ROLE_ID = "2af84b1e-32c8-42b7-82bc-daa82404023b"

# passwordValidityPeriodInDays value meaning "never expires"
_PASSWORD_NEVER_EXPIRES = 2147483647

# Minimum tenant-wide MFA registration coverage considered passing
_MFA_COVERAGE_THRESHOLD_PCT = 95.0


def _enabled_ca_policies(policies: list[dict]) -> list[dict]:
    return [p for p in policies if p.get("state") == "enabled"]


def _ca_requires_mfa(policy: dict) -> bool:
    controls = (policy.get("grantControls") or {}).get("builtInControls", [])
    return "mfa" in controls


def _security_defaults_enabled(asset: Asset) -> bool | None:
    defaults = prop(asset, "security_defaults")
    if defaults is None:
        return None
    return bool(defaults.get("isEnabled"))


@check("microsoft365/tenant", "CIS-M365-1.1.1")
def check_global_admin_count(asset: Asset) -> EvalResult | None:
    """Between two and four Global Administrator accounts are designated."""
    roles = prop(asset, "directory_roles")
    if roles is None:
        return None
    ga = next((r for r in roles if r.get("displayName") == "Global Administrator"), None)
    count = ga.get("member_count", 0) if ga else 0
    ok = 2 <= count <= 4
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"global_admin_count": count},
        description=f"{count} Global Administrator account(s); CIS recommends 2-4",
    )


@check("microsoft365/tenant", "CIS-M365-1.1.4")
def check_no_disabled_privileged_accounts(asset: Asset) -> EvalResult | None:
    """Disabled accounts should not hold privileged directory roles."""
    roles = prop(asset, "directory_roles")
    if roles is None:
        return None
    offenders = []
    for role in roles:
        for member in role.get("members", []):
            if member.get("accountEnabled") is False:
                offenders.append({"role": role.get("displayName"), "user": member.get("userPrincipalName")})
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"disabled_privileged_accounts": offenders[:20]},
        description=f"{len(offenders)} disabled account(s) still hold privileged roles"
        if offenders
        else "No disabled accounts hold privileged roles",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.1.1")
def check_security_defaults_or_ca(asset: Asset) -> EvalResult | None:
    """Security defaults or Conditional Access policies protect the tenant."""
    defaults_enabled = _security_defaults_enabled(asset)
    policies = prop(asset, "conditional_access_policies")
    if defaults_enabled is None and policies is None:
        return None
    enabled_policies = _enabled_ca_policies(policies or [])
    ok = bool(defaults_enabled) or bool(enabled_policies)
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={
            "security_defaults_enabled": bool(defaults_enabled),
            "enabled_ca_policy_count": len(enabled_policies),
        },
        description="Tenant has neither security defaults nor any enabled Conditional Access policy"
        if not ok
        else "Baseline identity protection is in place",
    )


@check("microsoft365/tenant", "CIS-M365-5.2.2.1")
def check_mfa_for_admins(asset: Asset) -> EvalResult | None:
    """MFA is enforced for administrative roles via CA (or security defaults)."""
    policies = prop(asset, "conditional_access_policies")
    if policies is None:
        return None
    if _security_defaults_enabled(asset):
        return EvalResult(
            status="pass",
            evidence={"via": "security_defaults"},
            description="Security defaults enforce MFA for administrators",
        )
    for policy in _enabled_ca_policies(policies):
        if not _ca_requires_mfa(policy):
            continue
        users = (policy.get("conditions") or {}).get("users", {})
        if users.get("includeRoles") or "All" in users.get("includeUsers", []):
            return EvalResult(
                status="pass",
                evidence={"policy": policy.get("displayName")},
                description=f"CA policy '{policy.get('displayName')}' requires MFA for admin roles",
            )
    return EvalResult(
        status="fail",
        evidence={"enabled_policy_count": len(_enabled_ca_policies(policies))},
        description="No enabled Conditional Access policy requires MFA for administrative roles",
    )


@check("microsoft365/tenant", "CIS-M365-5.2.2.2")
def check_mfa_for_all_users(asset: Asset) -> EvalResult | None:
    """MFA is enforced for all users via CA (or security defaults)."""
    policies = prop(asset, "conditional_access_policies")
    if policies is None:
        return None
    if _security_defaults_enabled(asset):
        return EvalResult(
            status="pass",
            evidence={"via": "security_defaults"},
            description="Security defaults enforce MFA for all users",
        )
    for policy in _enabled_ca_policies(policies):
        users = (policy.get("conditions") or {}).get("users", {})
        if _ca_requires_mfa(policy) and "All" in users.get("includeUsers", []):
            return EvalResult(
                status="pass",
                evidence={"policy": policy.get("displayName")},
                description=f"CA policy '{policy.get('displayName')}' requires MFA for all users",
            )
    return EvalResult(
        status="fail",
        evidence={"enabled_policy_count": len(_enabled_ca_policies(policies))},
        description="No enabled Conditional Access policy requires MFA for all users",
    )


@check("microsoft365/tenant", "CIS-M365-5.2.2.3")
def check_legacy_auth_blocked(asset: Asset) -> EvalResult | None:
    """Legacy authentication protocols are blocked."""
    policies = prop(asset, "conditional_access_policies")
    if policies is None:
        return None
    if _security_defaults_enabled(asset):
        return EvalResult(
            status="pass",
            evidence={"via": "security_defaults"},
            description="Security defaults block legacy authentication",
        )
    for policy in _enabled_ca_policies(policies):
        client_apps = (policy.get("conditions") or {}).get("clientAppTypes", [])
        controls = (policy.get("grantControls") or {}).get("builtInControls", [])
        if "block" in controls and ("exchangeActiveSync" in client_apps or "other" in client_apps):
            return EvalResult(
                status="pass",
                evidence={"policy": policy.get("displayName")},
                description=f"CA policy '{policy.get('displayName')}' blocks legacy authentication",
            )
    return EvalResult(
        status="fail",
        evidence={},
        description="No enabled Conditional Access policy blocks legacy authentication clients",
    )


@check("microsoft365/tenant", "CIS-M365-5.2.3.1")
def check_admin_mfa_registration(asset: Asset) -> EvalResult | None:
    """All administrators have registered MFA methods."""
    mfa = prop(asset, "mfa_registration")
    if mfa is None:
        return None
    missing = mfa.get("admin_mfa_not_registered", 0)
    total = mfa.get("admin_total", 0)
    return EvalResult(
        status="pass" if missing == 0 else "fail",
        evidence={"admin_total": total, "admin_mfa_not_registered": missing},
        description=f"{missing} of {total} administrator(s) have not registered MFA"
        if missing
        else f"All {total} administrator(s) have registered MFA",
    )


@check("microsoft365/tenant", "CIS-M365-5.2.3.2")
def check_user_mfa_registration(asset: Asset) -> EvalResult | None:
    """Tenant-wide MFA registration coverage meets the threshold."""
    mfa = prop(asset, "mfa_registration")
    if mfa is None:
        return None
    coverage = mfa.get("mfa_coverage_pct", 0)
    ok = coverage >= _MFA_COVERAGE_THRESHOLD_PCT
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={
            "mfa_coverage_pct": coverage,
            "threshold_pct": _MFA_COVERAGE_THRESHOLD_PCT,
            "mfa_not_registered": mfa.get("mfa_not_registered", 0),
        },
        description=f"MFA registration coverage is {coverage}% (threshold {_MFA_COVERAGE_THRESHOLD_PCT}%)",
    )


def _default_user_permissions(asset: Asset) -> dict | None:
    policy = prop(asset, "authorization_policy")
    if policy is None:
        return None
    return policy.get("defaultUserRolePermissions") or {}


@check("microsoft365/tenant", "CIS-M365-5.1.2.1")
def check_users_cannot_register_apps(asset: Asset) -> EvalResult | None:
    """Users cannot register their own applications."""
    perms = _default_user_permissions(asset)
    if perms is None:
        return None
    allowed = perms.get("allowedToCreateApps", True)
    return EvalResult(
        status="pass" if not allowed else "fail",
        evidence={"allowedToCreateApps": allowed},
        description="Users can register applications" if allowed else "App registration is restricted to admins",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.2.2")
def check_users_cannot_create_tenants(asset: Asset) -> EvalResult | None:
    """Users cannot create new tenants."""
    perms = _default_user_permissions(asset)
    if perms is None:
        return None
    allowed = perms.get("allowedToCreateTenants", True)
    return EvalResult(
        status="pass" if not allowed else "fail",
        evidence={"allowedToCreateTenants": allowed},
        description="Users can create tenants" if allowed else "Tenant creation is restricted to admins",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.2.3")
def check_users_cannot_create_security_groups(asset: Asset) -> EvalResult | None:
    """Users cannot create security groups."""
    perms = _default_user_permissions(asset)
    if perms is None:
        return None
    allowed = perms.get("allowedToCreateSecurityGroups", True)
    return EvalResult(
        status="pass" if not allowed else "fail",
        evidence={"allowedToCreateSecurityGroups": allowed},
        description="Users can create security groups"
        if allowed
        else "Security group creation is restricted to admins",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.5.1")
def check_user_consent_restricted(asset: Asset) -> EvalResult | None:
    """User consent to third-party applications is disabled or limited to
    low-impact permissions from verified publishers."""
    policy = prop(asset, "authorization_policy")
    if policy is None:
        return None
    grant_policies = (policy.get("defaultUserRolePermissions") or {}).get("permissionGrantPoliciesAssigned", [])
    ok = not grant_policies or all("low" in g.lower() for g in grant_policies)
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"permissionGrantPoliciesAssigned": grant_policies},
        description="Users can consent to apps for non-low-impact permissions"
        if not ok
        else "User app consent is disabled or limited to low-impact permissions",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.6.1")
def check_guest_invites_restricted(asset: Asset) -> EvalResult | None:
    """Guest invitations are limited to admins and guest-inviter roles."""
    policy = prop(asset, "authorization_policy")
    if policy is None:
        return None
    allow_from = policy.get("allowInvitesFrom") or "everyone"
    ok = allow_from in ("adminsAndGuestInviters", "none")
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"allowInvitesFrom": allow_from},
        description=f"Guest invitations allowed from: {allow_from}",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.6.2")
def check_guest_role_restricted(asset: Asset) -> EvalResult | None:
    """Guest users have the most restricted directory role."""
    policy = prop(asset, "authorization_policy")
    if policy is None:
        return None
    role_id = policy.get("guestUserRoleId") or ""
    ok = role_id == _RESTRICTED_GUEST_ROLE_ID
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"guestUserRoleId": role_id, "expected": _RESTRICTED_GUEST_ROLE_ID},
        description="Guest access is set to the most restricted role"
        if ok
        else "Guest users have broader directory access than 'restricted guest'",
    )


@check("microsoft365/tenant", "CIS-M365-5.1.3.1")
def check_passwords_never_expire(asset: Asset) -> EvalResult | None:
    """Password expiration is disabled (per modern NIST/CIS guidance)."""
    domains = prop(asset, "domains")
    if domains is None:
        return None
    offenders = [
        d.get("id")
        for d in domains
        if d.get("isVerified") and (d.get("passwordValidityPeriodInDays") or 0) not in (0, _PASSWORD_NEVER_EXPIRES)
    ]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"domains_with_expiration": offenders},
        description=f"{len(offenders)} domain(s) still expire passwords"
        if offenders
        else "Passwords are set to never expire on all verified domains",
    )


@check("microsoft365/tenant", "CIS-M365-5.2.3.3")
def check_weak_auth_methods_disabled(asset: Asset) -> EvalResult | None:
    """SMS and voice-call authentication methods are disabled."""
    policy = prop(asset, "auth_methods_policy")
    if policy is None:
        return None
    weak_enabled = []
    for config in policy.get("authenticationMethodConfigurations", []):
        if config.get("id", "").lower() in ("sms", "voice") and config.get("state") == "enabled":
            weak_enabled.append(config.get("id"))
    return EvalResult(
        status="pass" if not weak_enabled else "fail",
        evidence={"weak_methods_enabled": weak_enabled},
        description=f"Weak authentication methods enabled: {', '.join(weak_enabled)}"
        if weak_enabled
        else "SMS and voice authentication methods are disabled",
    )
