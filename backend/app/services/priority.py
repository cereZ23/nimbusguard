"""Priority/Triage layer — compute P0..P3 buckets for findings.

A finding's priority combines three axes:

1. **Severity** (``high`` | ``medium`` | ``low``) from the control definition.
2. **Effort** (``quick`` | ``moderate`` | ``refactor``) from the control
   definition (falls back to a default inferred from the control name).
3. **Exposure** (``internet`` | ``internal`` | ``none``) from the control
   definition (falls back to a default inferred from the resource type).

The base priority is looked up in a 3x3 matrix and is then bumped up by
one tier when the exposure is ``internet`` (internet-exposed findings are
strictly more urgent than internal ones at the same severity+effort).

The priority score (0-255) provides a finer-grained sort key inside the
same bucket, so that "HIGH+quick+internet" always sorts before
"HIGH+moderate+internet" even though they share the P0 label.
"""

from __future__ import annotations

from typing import Literal

Severity = Literal["high", "medium", "low"]
Effort = Literal["quick", "moderate", "refactor"]
Exposure = Literal["internet", "internal", "none"]
Priority = Literal["P0", "P1", "P2", "P3"]


# ── Priority buckets ─────────────────────────────────────────────────

# 3x3 base matrix: rows = severity, cols = effort.
# Readable shape:
#                  quick      moderate    refactor
#   high:            P0          P1          P2
#   medium:          P1          P2          P3
#   low:             P2          P3          P3
_BASE_MATRIX: dict[tuple[str, str], Priority] = {
    ("high", "quick"): "P0",
    ("high", "moderate"): "P1",
    ("high", "refactor"): "P2",
    ("medium", "quick"): "P1",
    ("medium", "moderate"): "P2",
    ("medium", "refactor"): "P3",
    ("low", "quick"): "P2",
    ("low", "moderate"): "P3",
    ("low", "refactor"): "P3",
}

# Single-tier bump for internet-exposed findings (capped at P0).
_BUMP_UP: dict[Priority, Priority] = {
    "P3": "P2",
    "P2": "P1",
    "P1": "P0",
    "P0": "P0",
}

_SEVERITY_WEIGHT = {"high": 100, "medium": 50, "low": 10}
_EFFORT_WEIGHT = {"quick": 60, "moderate": 30, "refactor": 10}
_EXPOSURE_BONUS = {"internet": 30, "internal": 10, "none": 0}


def compute_priority(
    severity: str | None,
    effort: str | None,
    exposure: str | None,
) -> Priority:
    """Return the priority bucket for a finding.

    Unknown/missing inputs fall back to the most conservative assumption:
    severity=medium, effort=moderate, exposure=none (which gives P2 by
    default — middle-of-the-road).
    """
    sev = (severity or "medium").lower()
    eff = (effort or "moderate").lower()
    exp = (exposure or "none").lower()

    # Guard against typos / unexpected values — default medium/moderate/none.
    if sev not in ("high", "medium", "low"):
        sev = "medium"
    if eff not in ("quick", "moderate", "refactor"):
        eff = "moderate"
    if exp not in ("internet", "internal", "none"):
        exp = "none"

    base = _BASE_MATRIX[(sev, eff)]
    if exp == "internet":
        base = _BUMP_UP[base]
    return base


def compute_priority_score(
    severity: str | None,
    effort: str | None,
    exposure: str | None,
) -> int:
    """Return a 0..255 sort key.

    Used to order findings *within* the same priority bucket. The formula
    is deterministic and stable: ``HIGH + quick + internet`` always sorts
    strictly higher than ``HIGH + moderate + internet``.
    """
    sev = (severity or "medium").lower()
    eff = (effort or "moderate").lower()
    exp = (exposure or "none").lower()
    return (
        _SEVERITY_WEIGHT.get(sev, _SEVERITY_WEIGHT["medium"])
        + _EFFORT_WEIGHT.get(eff, _EFFORT_WEIGHT["moderate"])
        + _EXPOSURE_BONUS.get(exp, _EXPOSURE_BONUS["none"])
    )


# ── Defaults — infer effort and exposure when the yaml doesn't specify ──

# Resource types that are reachable from the public internet either by
# design (web app, public IP) or by default (storage account, SQL server).
_INTERNET_EXPOSED_RESOURCE_TYPES = {
    "microsoft.network/networksecuritygroups",
    "microsoft.network/publicipaddresses",
    "microsoft.network/applicationgateways",
    "microsoft.network/frontdoors",
    "microsoft.network/azurefirewalls",
    "microsoft.network/virtualnetworkgateways",
    "microsoft.web/sites",
    "microsoft.storage/storageaccounts",
    "microsoft.sql/servers",
    "microsoft.sql/servers/databases",
    "microsoft.dbforpostgresql/flexibleservers",
    "microsoft.dbformysql/flexibleservers",
    "microsoft.documentdb/databaseaccounts",
    "microsoft.containerregistry/registries",
    "microsoft.containerservice/managedclusters",
    "microsoft.keyvault/vaults",
    "aws.s3.bucket",
    "aws.ec2.instance",
    "aws.ec2.security-group",
    "aws.rds.instance",
    "aws.lambda.function",
}

# Keywords inside control names that strongly suggest how hard the fix is.
# Order matters: refactor wins over moderate wins over quick.
_REFACTOR_KEYWORDS = (
    "customer-managed",
    "customer managed",
    " cmk",
    "cmk encryption",
    "cmk ",
    "encryption with cmk",
    "private endpoint",
    "private link",
    "vnet integration",
    "recreate",
    "migrate",
    "bring your own key",
    "dns endpoint",
    "infrastructure encryption",
    "trusted launch",
    "confidential vm",
)
_MODERATE_KEYWORDS = (
    "integration",  # any non-VNet integration (AAD, Jira, etc.)
    "policy",
    "tier",
    "ip restrict",
    "network rule",
    "network acl",
    "managed identity",
    "auth settings",
    "conditional access",
    "workload identity",
    "azure rbac",
    "diagnostic setting",
    "retention",
    "backup",
    "zone redundan",
    "cross-region",
    "contact",
    "auto-provisioning",
)
_QUICK_KEYWORDS = (
    "enabled",
    "disabled",
    "restrict",
    "configured",
    "set",
    "disable",
    "enable",
    "block",
    "off",
    "closed",
    "cipher",
    "anonymous pull",
    "quarantine",
    "content trust",
    # TLS / HTTPS hardening is a single portal toggle most of the time.
    "tls",
    "https",
    "enforced",
    "public access",
    "public network",
)


def default_effort(control_name: str | None) -> Effort:
    """Infer the effort bucket from the control's human-readable name.

    The logic is intentionally simple — a substring match against three
    keyword lists. It's used as a fallback when the yaml doesn't carry
    an explicit ``effort`` field on a control. Expected to be overridden
    by an explicit yaml value for controls that don't fit the defaults.
    """
    if not control_name:
        return "moderate"
    lowered = control_name.lower()
    for kw in _REFACTOR_KEYWORDS:
        if kw in lowered:
            return "refactor"
    for kw in _MODERATE_KEYWORDS:
        if kw in lowered:
            return "moderate"
    for kw in _QUICK_KEYWORDS:
        if kw in lowered:
            return "quick"
    return "moderate"


def default_exposure(resource_type: str | None) -> Exposure:
    """Infer exposure from the resource type the control targets.

    Resources in ``_INTERNET_EXPOSED_RESOURCE_TYPES`` default to
    ``internet``; everything else defaults to ``internal``. The special
    ``microsoft.subscription/subscription`` synthetic asset is
    ``internal`` because the subscription-level posture doesn't have a
    single exposed endpoint.
    """
    if not resource_type:
        return "internal"
    rt = resource_type.lower()
    if rt in _INTERNET_EXPOSED_RESOURCE_TYPES:
        return "internet"
    return "internal"


# ── Secure Score projection ─────────────────────────────────────────


def project_secure_score_after_fixing(
    current_pass: int,
    current_fail: int,
    fixed_fail: int,
) -> float:
    """Return the secure score (0-100) assuming ``fixed_fail`` failing
    findings are resolved (become pass).

    Used by the dashboard to display "fix P0 → +15% score" motivation.
    """
    total = current_pass + current_fail
    if total == 0:
        return 0.0
    new_pass = current_pass + fixed_fail
    return round((new_pass / total) * 100.0, 1)
