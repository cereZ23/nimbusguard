"""Entra ID / Azure AD checks (CIS-AZ-01, CIS-AZ-02).

These checks evaluate the synthetic `microsoft.entra/tenant` asset created
by `entra_collector.py`. They assess MFA enforcement via two complementary
signals:

1. **Conditional Access policies** — is there an enabled policy that requires
   MFA for the target population (admins for CIS-AZ-01, all users for CIS-AZ-02)?
2. **MFA registration summary** — what percentage of users/admins have actually
   registered an MFA method?

Both signals are needed: a CA policy requiring MFA is necessary but not
sufficient (users may not have registered), and registration alone doesn't
mean enforcement (a user can register but the policy may not require it).
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


def _has_ca_policy_requiring_mfa(
    policies: list[dict],
    *,
    require_all_users: bool = False,
) -> tuple[bool, str | None]:
    """Check if any enabled Conditional Access policy requires MFA.

    Args:
        policies: list of CA policy objects from Graph API
        require_all_users: if True, the policy must target "All" users;
            if False, it must target at least admin/privileged roles.

    Returns:
        (found, policy_name) tuple.
    """
    for policy in policies:
        if policy.get("state") != "enabled":
            continue

        conditions = policy.get("conditions", {})
        users = conditions.get("users", {})
        grant = policy.get("grantControls", {})

        # Check if grant requires MFA
        built_in_controls = grant.get("builtInControls", [])
        if "mfa" not in built_in_controls:
            continue

        if require_all_users:
            # Must include "All" in includeUsers
            include_users = users.get("includeUsers", [])
            if "All" in include_users:
                return True, policy.get("displayName")
        else:
            # Must include admin roles or "All"
            include_users = users.get("includeUsers", [])
            include_roles = users.get("includeRoles", [])
            if "All" in include_users or include_roles:
                return True, policy.get("displayName")

    return False, None


@check("microsoft.entra/tenant", "CIS-AZ-01")
def check_mfa_privileged_users(asset: Asset) -> EvalResult:
    """CIS-AZ-01: MFA should be enabled for all privileged users.

    Checks for:
    1. A Conditional Access policy that requires MFA for admin roles.
    2. All privileged users have registered MFA.
    """
    props = asset.raw_properties or {}
    policies = props.get("conditional_access_policies", [])
    mfa_reg = props.get("mfa_registration", {})

    # Check 1: CA policy requiring MFA for admins
    has_policy, policy_name = _has_ca_policy_requiring_mfa(policies, require_all_users=False)

    # Check 2: Admin MFA registration
    admin_total = mfa_reg.get("admin_total", 0)
    admin_mfa = mfa_reg.get("admin_mfa_registered", 0)
    admin_no_mfa = mfa_reg.get("admin_mfa_not_registered", 0)

    evidence = {
        "ca_policy_mfa_admins": has_policy,
        "ca_policy_name": policy_name,
        "admin_total": admin_total,
        "admin_mfa_registered": admin_mfa,
        "admin_mfa_not_registered": admin_no_mfa,
    }

    if not policies and not mfa_reg:
        return EvalResult(
            status="fail",
            evidence=evidence,
            description=(
                "Unable to assess MFA for privileged users — Entra ID data not available. "
                "Ensure the service principal has Directory.Read.All and Policy.Read.All permissions."
            ),
        )

    # Pass if: CA policy exists AND all admins have MFA registered
    if has_policy and admin_no_mfa == 0 and admin_total > 0:
        return EvalResult(
            status="pass",
            evidence=evidence,
            description=(
                f"MFA is enforced for privileged users via Conditional Access policy "
                f"'{policy_name}'. All {admin_total} admin accounts have MFA registered."
            ),
        )

    # Build specific failure message
    issues = []
    if not has_policy:
        issues.append("No Conditional Access policy found that requires MFA for admin/privileged roles")
    if admin_no_mfa > 0:
        issues.append(f"{admin_no_mfa} of {admin_total} privileged users have NOT registered MFA")

    return EvalResult(
        status="fail",
        evidence=evidence,
        description=" | ".join(issues),
    )


@check("microsoft.entra/tenant", "CIS-AZ-02")
def check_mfa_all_users(asset: Asset) -> EvalResult:
    """CIS-AZ-02: MFA should be enabled for all users.

    Checks for:
    1. A Conditional Access policy that requires MFA for ALL users.
    2. MFA registration coverage across all users.
    """
    props = asset.raw_properties or {}
    policies = props.get("conditional_access_policies", [])
    mfa_reg = props.get("mfa_registration", {})

    # Check 1: CA policy requiring MFA for all users
    has_policy, policy_name = _has_ca_policy_requiring_mfa(policies, require_all_users=True)

    # Check 2: MFA registration coverage
    total = mfa_reg.get("total_users", 0)
    registered = mfa_reg.get("mfa_registered", 0)
    not_registered = mfa_reg.get("mfa_not_registered", 0)
    coverage_pct = mfa_reg.get("mfa_coverage_pct", 0)

    evidence = {
        "ca_policy_mfa_all_users": has_policy,
        "ca_policy_name": policy_name,
        "total_users": total,
        "mfa_registered": registered,
        "mfa_not_registered": not_registered,
        "mfa_coverage_pct": coverage_pct,
    }

    if not policies and not mfa_reg:
        return EvalResult(
            status="fail",
            evidence=evidence,
            description=(
                "Unable to assess MFA for all users — Entra ID data not available. "
                "Ensure the service principal has Directory.Read.All and Policy.Read.All permissions."
            ),
        )

    # Pass if: CA policy for all users AND coverage >= 95%
    if has_policy and coverage_pct >= 95:
        return EvalResult(
            status="pass",
            evidence=evidence,
            description=(
                f"MFA is enforced for all users via Conditional Access policy "
                f"'{policy_name}'. {coverage_pct}% of users ({registered}/{total}) "
                f"have MFA registered."
            ),
        )

    issues = []
    if not has_policy:
        issues.append("No Conditional Access policy found that requires MFA for ALL users")
    if coverage_pct < 95:
        issues.append(f"MFA registration coverage is {coverage_pct}% ({not_registered} users without MFA)")

    return EvalResult(
        status="fail",
        evidence=evidence,
        description=" | ".join(issues),
    )
