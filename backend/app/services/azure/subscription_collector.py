"""Subscription-level state collector.

Fetches security posture data that does NOT live in Resource Graph but is owned
by the subscription itself:

- Defender for Cloud pricing tiers (via Microsoft.Security/pricings)
- Security contacts (via Microsoft.Security/securityContacts)
- Auto-provisioning settings (via Microsoft.Security/autoProvisioningSettings)
- Subscription owner role assignment count (via Microsoft.Authorization)

The collector is designed for graceful degradation: if one Azure API call
fails, the others continue and the failure is recorded in the returned dict so
checks can skip gracefully. This prevents a single API hiccup (or missing
permission on a brand-new subscription) from poisoning the whole scan.

The collected dict is persisted as a synthetic Asset with
``resource_type="microsoft.subscription/subscription"`` so the existing
evaluator framework picks it up automatically.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

from azure.identity import ClientSecretCredential

logger = logging.getLogger(__name__)


# Defender pricing tier that represents the paid / enabled state.
# Free = disabled (no Defender protection), Standard = enabled.
_DEFENDER_ENABLED_TIER = "Standard"


async def _run_sync(func, *args, **kwargs):
    """Run a synchronous Azure SDK call in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


async def collect_subscription_state(
    credential: ClientSecretCredential,
    subscription_id: str,
) -> dict[str, Any]:
    """Collect subscription-level security state.

    Returns a dict with keys ``defender_plans``, ``security_contacts``,
    ``auto_provisioning``, ``owner_count``, ``_errors`` (list of collection
    failures). Individual keys are ``None`` if the corresponding API call
    failed. The dict is suitable for use as ``Asset.raw_properties``.
    """
    state: dict[str, Any] = {
        "subscription_id": subscription_id,
        "defender_plans": None,
        "security_contacts": None,
        "auto_provisioning": None,
        "owner_count": None,
        "_errors": [],
    }

    # Defender for Cloud plans — Microsoft.Security/pricings
    try:
        from azure.mgmt.security import SecurityCenter

        sec_client = SecurityCenter(credential, subscription_id)
        pricings_iter = await _run_sync(sec_client.pricings.list)
        # The SDK returns a PagedResult-style object; list() returns an iterable.
        plans: dict[str, str] = {}
        for pricing in pricings_iter.value or []:
            name = getattr(pricing, "name", None) or ""
            tier = getattr(pricing, "pricing_tier", None) or "Free"
            if name:
                plans[name] = tier
        state["defender_plans"] = plans
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to collect Defender pricings for %s: %s", subscription_id, exc)
        state["_errors"].append({"source": "defender_plans", "error": str(exc)})

    # Security contacts — Microsoft.Security/securityContacts
    try:
        from azure.mgmt.security import SecurityCenter

        sec_client = SecurityCenter(credential, subscription_id)
        contacts_iter = await _run_sync(sec_client.security_contacts.list)
        contacts: list[dict[str, Any]] = []
        for contact in contacts_iter or []:
            contacts.append(
                {
                    "email": getattr(contact, "email", None) or getattr(contact, "emails", None),
                    "alert_notifications": _extract_alert_notifications(contact),
                }
            )
        state["security_contacts"] = contacts
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to collect security contacts for %s: %s", subscription_id, exc)
        state["_errors"].append({"source": "security_contacts", "error": str(exc)})

    # Auto-provisioning settings — Microsoft.Security/autoProvisioningSettings
    try:
        from azure.mgmt.security import SecurityCenter

        sec_client = SecurityCenter(credential, subscription_id)
        settings = await _run_sync(sec_client.auto_provisioning_settings.get, "default")
        # auto_provision is "On" / "Off"
        state["auto_provisioning"] = getattr(settings, "auto_provision", None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to collect auto-provisioning settings for %s: %s", subscription_id, exc)
        state["_errors"].append({"source": "auto_provisioning", "error": str(exc)})

    # Subscription owner count — Microsoft.Authorization/roleAssignments
    try:
        from azure.mgmt.authorization import AuthorizationManagementClient

        auth_client = AuthorizationManagementClient(credential, subscription_id)
        assignments_iter = await _run_sync(auth_client.role_assignments.list_for_subscription)

        owner_count = 0
        for assignment in assignments_iter or []:
            role_def_id = getattr(assignment, "role_definition_id", "") or ""
            # The built-in Owner role definition ID ends with
            # /8e3af657-a8ff-443c-a75c-2fe8c4bcb635 across all subscriptions.
            if role_def_id.endswith("/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"):
                owner_count += 1
        state["owner_count"] = owner_count
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to collect owner role assignments for %s: %s", subscription_id, exc)
        state["_errors"].append({"source": "owner_count", "error": str(exc)})

    return state


def _extract_alert_notifications(contact: Any) -> bool | None:
    """Extract alert_notifications flag from the security contact object.

    The Azure SDK returns different shapes depending on the API version. Old
    versions expose ``alert_notifications = "On" | "Off"`` as a string, newer
    versions expose ``alert_notifications = AlertNotifications(state="On")``.
    This helper normalises to a boolean or None.
    """
    raw = getattr(contact, "alert_notifications", None)
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.lower() == "on"
    # Object style: AlertNotifications(state="On", minimal_severity="Low")
    state_val = getattr(raw, "state", None)
    if isinstance(state_val, str):
        return state_val.lower() == "on"
    return None


def is_defender_plan_enabled(defender_plans: dict[str, str] | None, plan_name: str) -> bool:
    """Return True if the given Defender plan is enabled (Standard tier)."""
    if not isinstance(defender_plans, dict):
        return False
    tier = defender_plans.get(plan_name)
    return tier == _DEFENDER_ENABLED_TIER
