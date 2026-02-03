"""IAM checks (CIS-AWS-09, 10, 11, 12)."""
from __future__ import annotations

from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.iam.account-summary", "CIS-AWS-09")
def check_root_mfa(asset: Asset) -> EvalResult:
    """CIS-AWS-09: Root account should have MFA enabled."""
    props = asset.raw_properties or {}
    summary = props.get("SummaryMap") or props
    root_mfa = summary.get("AccountMFAEnabled", 0)
    is_enabled = int(root_mfa) == 1
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"AccountMFAEnabled": root_mfa},
        description="Root account MFA is enabled"
        if is_enabled
        else "Root account MFA is NOT enabled -- enable immediately",
    )


@check("aws.iam.user", "CIS-AWS-10")
def check_user_mfa(asset: Asset) -> EvalResult:
    """CIS-AWS-10: IAM users with console access should have MFA enabled."""
    props = asset.raw_properties or {}
    has_login_profile = props.get("HasLoginProfile", False)
    mfa_devices = props.get("MFADevices") or []
    has_mfa = len(mfa_devices) > 0

    # If user has no console access, MFA is not required
    if not has_login_profile:
        return EvalResult(
            status="pass",
            evidence={
                "HasLoginProfile": False,
                "MFADevices": 0,
            },
            description="User does not have console access (no login profile)",
        )

    return EvalResult(
        status="pass" if has_mfa else "fail",
        evidence={
            "HasLoginProfile": has_login_profile,
            "MFADevices": len(mfa_devices),
        },
        description="MFA is enabled for console user"
        if has_mfa
        else "MFA is NOT enabled for a user with console access",
    )


@check("aws.iam.password-policy", "CIS-AWS-11")
def check_password_policy(asset: Asset) -> EvalResult:
    """CIS-AWS-11: IAM password policy should meet minimum requirements."""
    props = asset.raw_properties or {}
    min_length = props.get("MinimumPasswordLength", 0)
    require_symbols = props.get("RequireSymbols", False)
    require_numbers = props.get("RequireNumbers", False)
    require_upper = props.get("RequireUppercaseCharacters", False)
    require_lower = props.get("RequireLowercaseCharacters", False)
    max_age = props.get("MaxPasswordAge", 0)
    prevent_reuse = props.get("PasswordReusePrevention", 0)

    issues = []
    if min_length < 14:
        issues.append(f"MinimumPasswordLength={min_length} (should be >= 14)")
    if not require_symbols:
        issues.append("RequireSymbols is disabled")
    if not require_numbers:
        issues.append("RequireNumbers is disabled")
    if not require_upper:
        issues.append("RequireUppercaseCharacters is disabled")
    if not require_lower:
        issues.append("RequireLowercaseCharacters is disabled")
    if max_age == 0 or max_age > 90:
        issues.append(f"MaxPasswordAge={max_age} (should be <= 90)")
    if prevent_reuse < 24:
        issues.append(f"PasswordReusePrevention={prevent_reuse} (should be >= 24)")

    is_compliant = len(issues) == 0

    return EvalResult(
        status="pass" if is_compliant else "fail",
        evidence={
            "MinimumPasswordLength": min_length,
            "RequireSymbols": require_symbols,
            "RequireNumbers": require_numbers,
            "RequireUppercaseCharacters": require_upper,
            "RequireLowercaseCharacters": require_lower,
            "MaxPasswordAge": max_age,
            "PasswordReusePrevention": prevent_reuse,
            "issues": issues,
        },
        description="Password policy meets CIS requirements"
        if is_compliant
        else f"Password policy issues: {'; '.join(issues)}",
    )


@check("aws.iam.user", "CIS-AWS-12")
def check_access_key_rotation(asset: Asset) -> EvalResult:
    """CIS-AWS-12: IAM access keys should be rotated within 90 days."""
    props = asset.raw_properties or {}
    access_keys = props.get("AccessKeys") or []

    if not access_keys:
        return EvalResult(
            status="pass",
            evidence={"AccessKeys": 0},
            description="No access keys found for this user",
        )

    stale_keys = []
    now = datetime.now(UTC)

    for key in access_keys:
        key_status = key.get("Status", "")
        if key_status != "Active":
            continue

        create_date_str = key.get("CreateDate", "")
        if not create_date_str:
            stale_keys.append({"AccessKeyId": key.get("AccessKeyId"), "reason": "no CreateDate"})
            continue

        try:
            if isinstance(create_date_str, datetime):
                create_date = create_date_str
            else:
                create_date = datetime.fromisoformat(create_date_str.replace("Z", "+00:00"))
            age_days = (now - create_date).days
            if age_days > 90:
                stale_keys.append({
                    "AccessKeyId": key.get("AccessKeyId"),
                    "age_days": age_days,
                })
        except (ValueError, TypeError):
            stale_keys.append({"AccessKeyId": key.get("AccessKeyId"), "reason": "unparseable date"})

    return EvalResult(
        status="fail" if stale_keys else "pass",
        evidence={
            "total_keys": len(access_keys),
            "stale_keys": stale_keys,
        },
        description=f"{len(stale_keys)} access key(s) older than 90 days"
        if stale_keys
        else "All active access keys are within the 90-day rotation window",
    )
