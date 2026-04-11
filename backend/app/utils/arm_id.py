"""Azure Resource Manager (ARM) ID parser.

Extracts structured parts from ARM resource IDs so remediation snippets
can be rendered with the customer's real subscription / resource group /
resource name instead of placeholders.

Example ARM ID:
    /subscriptions/xxx/resourceGroups/rg-prod/providers/Microsoft.Web/sites/myapp

parses to:
    ArmId(
        subscription_id="xxx",
        resource_group="rg-prod",
        provider_namespace="Microsoft.Web",
        resource_type="sites",
        name="myapp",
        parent_path=None,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ArmId:
    """Structured view over an Azure ARM resource ID."""

    subscription_id: str
    resource_group: str | None
    provider_namespace: str
    resource_type: str
    name: str
    parent_path: str | None = None

    def as_template_vars(self) -> dict[str, str]:
        """Return a flat dict suitable for `str.format(**vars)` substitution.

        Keys are stable and documented in the CONTRIBUTING guide so snippet
        authors can rely on them:

            {subscription_id}   full subscription GUID
            {resource_group}    resource group name (empty string if None)
            {name}              leaf resource name
            {resource_type}     leaf resource type (e.g. "sites")
            {provider}          provider namespace (e.g. "Microsoft.Web")
            {full_type}         "Microsoft.Web/sites"
        """
        return {
            "subscription_id": self.subscription_id,
            "resource_group": self.resource_group or "",
            "name": self.name,
            "resource_type": self.resource_type,
            "provider": self.provider_namespace,
            "full_type": f"{self.provider_namespace}/{self.resource_type}",
        }


def parse_provider_id(provider_id: str | None) -> ArmId | None:
    """Parse an Azure ARM ID into an `ArmId` dataclass.

    Returns `None` for null / empty input or for IDs that do not match the
    canonical `/subscriptions/{id}/resourceGroups/{rg}/providers/...` shape.
    Caller is expected to fall back to the un-rendered template when parsing
    fails so the UI degrades gracefully on non-Azure assets (e.g. AWS, or
    synthetic subscription-scope assets).

    Lookups are case-insensitive on the segment keywords (`subscriptions`,
    `resourceGroups`, `providers`) because the Azure API returns mixed case
    depending on endpoint.
    """
    if not provider_id:
        return None

    parts = provider_id.strip("/").split("/")
    if len(parts) < 2:
        return None

    # Normalise segment keywords to lowercase for matching while preserving
    # the original values.
    lowered = [p.lower() for p in parts]

    try:
        sub_idx = lowered.index("subscriptions")
        subscription_id = parts[sub_idx + 1]
    except (ValueError, IndexError):
        return None

    resource_group: str | None = None
    if "resourcegroups" in lowered:
        rg_idx = lowered.index("resourcegroups")
        try:
            resource_group = parts[rg_idx + 1]
        except IndexError:
            return None
    elif "resourcegroup" in lowered:  # defensive: some APIs drop the 's'
        rg_idx = lowered.index("resourcegroup")
        try:
            resource_group = parts[rg_idx + 1]
        except IndexError:
            return None

    if "providers" not in lowered:
        # Subscription-scope or management-group-scope asset — we only have
        # the subscription_id and that's enough for Defender-style snippets.
        return ArmId(
            subscription_id=subscription_id,
            resource_group=resource_group,
            provider_namespace="",
            resource_type="",
            name=parts[-1] if parts else "",
        )

    prov_idx = lowered.index("providers")
    try:
        provider_namespace = parts[prov_idx + 1]
    except IndexError:
        return None

    # Everything after `providers/{namespace}/` is a list of (type, name)
    # pairs. The last pair is the leaf resource; anything before is the
    # parent path (e.g. vaults/keys).
    tail = parts[prov_idx + 2 :]
    if len(tail) < 2 or len(tail) % 2 != 0:
        return None

    leaf_type = tail[-2]
    leaf_name = tail[-1]

    parent_path: str | None = None
    if len(tail) > 2:
        parent_path = "/".join(tail[:-2])

    return ArmId(
        subscription_id=subscription_id,
        resource_group=resource_group,
        provider_namespace=provider_namespace,
        resource_type=leaf_type,
        name=leaf_name,
        parent_path=parent_path,
    )
