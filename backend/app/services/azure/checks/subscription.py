"""Subscription-level Azure security checks (CIS-AZ-104..113).

These checks run on the synthetic asset produced by
``subscription_collector.collect_subscription_state()``. The asset's
``raw_properties`` has the shape::

    {
        "subscription_id": "...",
        "defender_plans": {"VirtualMachines": "Standard", ...} | None,
        "security_contacts": [{"email": "...", "alert_notifications": True}] | None,
        "auto_provisioning": "On" | "Off" | None,
        "owner_count": 2 | None,
        "_errors": [{"source": "...", "error": "..."}],
    }

Any top-level field may be ``None`` if the corresponding Azure API call
failed at collection time. In that case the affected check reports ``fail``
with an evidence entry pointing at the collection error, so the user is
nudged to fix the permission or connectivity problem instead of silently
passing.
"""

from __future__ import annotations

from typing import Any

from app.models.asset import Asset
from app.services.azure.subscription_collector import is_defender_plan_enabled
from app.services.evaluator import EvalResult, check

# Maximum number of built-in Owner role assignments considered acceptable
# at the subscription scope. CIS recommends <= 3 to minimise blast radius.
_MAX_OWNERS = 3


def _collection_error_for(props: dict[str, Any], source: str) -> str | None:
    """Return the collector error message for a given source, if any."""
    errors = props.get("_errors") or []
    if not isinstance(errors, list):
        return None
    for err in errors:
        if isinstance(err, dict) and err.get("source") == source:
            return err.get("error")
    return None


def _defender_plan_check(asset: Asset, plan_name: str, friendly_name: str) -> EvalResult:
    """Shared implementation for Defender-for-X pricing tier checks."""
    props = asset.raw_properties or {}
    plans = props.get("defender_plans")
    err = _collection_error_for(props, "defender_plans")
    if err:
        return EvalResult(
            status="fail",
            evidence={"collector_error": err},
            description=(
                f"Could not determine Defender for {friendly_name} state — "
                "Security Center pricing API call failed. Grant Security Reader and retry."
            ),
        )
    enabled = is_defender_plan_enabled(plans, plan_name)
    tier = (plans or {}).get(plan_name, "Free") if isinstance(plans, dict) else "unknown"
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"plan": plan_name, "tier": tier},
        description=(
            f"Defender for {friendly_name} is enabled (tier: {tier})"
            if enabled
            else (
                f"Defender for {friendly_name} is NOT enabled (tier: {tier}) — "
                "enable the Standard plan in Microsoft Defender for Cloud to get "
                "runtime threat detection for this workload type"
            )
        ),
    )


@check("microsoft.subscription/subscription", "CIS-AZ-104")
def check_defender_for_servers(asset: Asset) -> EvalResult:
    """CIS-AZ-104: Microsoft Defender for Servers should be enabled."""
    return _defender_plan_check(asset, "VirtualMachines", "Servers")


@check("microsoft.subscription/subscription", "CIS-AZ-105")
def check_defender_for_storage(asset: Asset) -> EvalResult:
    """CIS-AZ-105: Microsoft Defender for Storage should be enabled."""
    return _defender_plan_check(asset, "StorageAccounts", "Storage")


@check("microsoft.subscription/subscription", "CIS-AZ-106")
def check_defender_for_sql(asset: Asset) -> EvalResult:
    """CIS-AZ-106: Microsoft Defender for SQL servers should be enabled."""
    return _defender_plan_check(asset, "SqlServers", "SQL servers")


@check("microsoft.subscription/subscription", "CIS-AZ-107")
def check_defender_for_app_service(asset: Asset) -> EvalResult:
    """CIS-AZ-107: Microsoft Defender for App Service should be enabled."""
    return _defender_plan_check(asset, "AppServices", "App Service")


@check("microsoft.subscription/subscription", "CIS-AZ-108")
def check_defender_for_containers(asset: Asset) -> EvalResult:
    """CIS-AZ-108: Microsoft Defender for Containers should be enabled."""
    return _defender_plan_check(asset, "Containers", "Containers")


@check("microsoft.subscription/subscription", "CIS-AZ-109")
def check_defender_for_key_vault(asset: Asset) -> EvalResult:
    """CIS-AZ-109: Microsoft Defender for Key Vault should be enabled."""
    return _defender_plan_check(asset, "KeyVaults", "Key Vault")


@check("microsoft.subscription/subscription", "CIS-AZ-110")
def check_security_contact_email(asset: Asset) -> EvalResult:
    """CIS-AZ-110: Subscription should have a security contact email configured."""
    props = asset.raw_properties or {}
    contacts = props.get("security_contacts")
    err = _collection_error_for(props, "security_contacts")
    if err:
        return EvalResult(
            status="fail",
            evidence={"collector_error": err},
            description="Could not determine security contacts — collection failed",
        )
    if not isinstance(contacts, list) or not contacts:
        return EvalResult(
            status="fail",
            evidence={"contacts_count": 0},
            description=(
                "No security contact configured — Microsoft Defender for Cloud has "
                "no address to notify on high-severity alerts"
            ),
        )
    has_email = any((isinstance(c, dict) and (c.get("email") or c.get("emails"))) for c in contacts)
    return EvalResult(
        status="pass" if has_email else "fail",
        evidence={"contacts_count": len(contacts)},
        description=(
            f"{len(contacts)} security contact(s) with email configured"
            if has_email
            else "Security contacts exist but none has an email address"
        ),
    )


@check("microsoft.subscription/subscription", "CIS-AZ-111")
def check_security_contact_alert_notifications(asset: Asset) -> EvalResult:
    """CIS-AZ-111: Security contact alert notifications should be enabled."""
    props = asset.raw_properties or {}
    contacts = props.get("security_contacts")
    err = _collection_error_for(props, "security_contacts")
    if err:
        return EvalResult(
            status="fail",
            evidence={"collector_error": err},
            description="Could not determine security contacts — collection failed",
        )
    if not isinstance(contacts, list) or not contacts:
        return EvalResult(
            status="fail",
            evidence={"contacts_count": 0},
            description="No security contact configured — cannot enable alert notifications",
        )
    has_notifications = any((isinstance(c, dict) and c.get("alert_notifications") is True) for c in contacts)
    return EvalResult(
        status="pass" if has_notifications else "fail",
        evidence={"contacts_count": len(contacts)},
        description=(
            "At least one security contact has alert notifications enabled"
            if has_notifications
            else (
                "No security contact has alert notifications enabled — "
                "Defender for Cloud will not send email alerts on high-severity findings"
            )
        ),
    )


@check("microsoft.subscription/subscription", "CIS-AZ-112")
def check_auto_provisioning_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-112: Auto-provisioning of the Log Analytics agent should be enabled."""
    props = asset.raw_properties or {}
    auto_prov = props.get("auto_provisioning")
    err = _collection_error_for(props, "auto_provisioning")
    if err:
        return EvalResult(
            status="fail",
            evidence={"collector_error": err},
            description="Could not determine auto-provisioning state — collection failed",
        )
    if not isinstance(auto_prov, str):
        return EvalResult(
            status="fail",
            evidence={"auto_provisioning": auto_prov},
            description="Auto-provisioning setting is not configured",
        )
    is_on = auto_prov.lower() == "on"
    return EvalResult(
        status="pass" if is_on else "fail",
        evidence={"auto_provisioning": auto_prov},
        description=(
            f"Auto-provisioning is {auto_prov} — agents are deployed automatically on new VMs"
            if is_on
            else (
                f"Auto-provisioning is {auto_prov} — new VMs will not get the Log Analytics "
                "agent automatically, limiting Defender's visibility"
            )
        ),
    )


@check("microsoft.subscription/subscription", "CIS-AZ-113")
def check_subscription_owner_count(asset: Asset) -> EvalResult:
    """CIS-AZ-113: Subscription should have no more than 3 Owner role assignments."""
    props = asset.raw_properties or {}
    count = props.get("owner_count")
    err = _collection_error_for(props, "owner_count")
    if err:
        return EvalResult(
            status="fail",
            evidence={"collector_error": err},
            description="Could not enumerate Owner role assignments — collection failed",
        )
    if not isinstance(count, int):
        return EvalResult(
            status="fail",
            evidence={"owner_count": count},
            description="Owner role assignment count is unknown",
        )
    ok = count <= _MAX_OWNERS
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"owner_count": count, "max_allowed": _MAX_OWNERS},
        description=(
            f"Subscription has {count} Owner(s) (<= {_MAX_OWNERS})"
            if ok
            else (
                f"Subscription has {count} Owner(s) — exceeds the recommended maximum "
                f"of {_MAX_OWNERS}. Reduce the blast radius by downgrading extra Owner "
                "assignments to Contributor or a custom least-privilege role."
            )
        ),
    )
