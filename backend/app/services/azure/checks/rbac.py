"""RBAC / Role Definition checks (CIS-AZ-03)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.authorization/roledefinitions", "CIS-AZ-03")
def check_no_custom_owner_roles(asset: Asset) -> EvalResult:
    """CIS-AZ-03: Custom subscription owner roles should not exist."""
    props = asset.raw_properties or {}

    # Only flag custom roles (not built-in)
    role_type = props.get("type", props.get("roleType", ""))
    if str(role_type).lower() != "customrole":
        return EvalResult(
            status="pass",
            evidence={"roleType": role_type, "isCustom": False},
            description="Built-in role — not applicable",
        )

    # Check if the role has wildcard actions at subscription scope
    permissions = props.get("permissions", [])
    assignable_scopes = props.get("assignableScopes", [])

    has_wildcard_actions = False
    for perm in permissions:
        actions = perm.get("actions", []) if isinstance(perm, dict) else []
        if "*" in actions:
            has_wildcard_actions = True
            break

    has_sub_scope = False
    for scope in assignable_scopes:
        s = scope.rstrip("/")
        # Match "/" or "/subscriptions/{id}" but not deeper scopes like resourceGroups
        if s == "" or s == "/":
            has_sub_scope = True
            break
        parts = s.split("/")
        # "/subscriptions/{id}" splits to ["", "subscriptions", "{id}"]
        if len(parts) == 3 and parts[1].lower() == "subscriptions":
            has_sub_scope = True
            break

    is_owner_like = has_wildcard_actions and has_sub_scope
    return EvalResult(
        status="fail" if is_owner_like else "pass",
        evidence={
            "roleType": role_type,
            "has_wildcard_actions": has_wildcard_actions,
            "has_subscription_scope": has_sub_scope,
        },
        description="Custom role with owner-level permissions at subscription scope — remove or restrict"
        if is_owner_like
        else "Custom role does not have owner-level permissions",
    )
