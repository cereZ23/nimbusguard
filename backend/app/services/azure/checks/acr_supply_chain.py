"""Azure Container Registry supply-chain checks (CIS-AZ-135..140).

Complements the baseline ACR checks in ``container_registry.py`` (admin
user disabled, public network access disabled) with supply-chain hardening
controls that matter for container security: anonymous pull, network ACL
default deny, quarantine policy, content trust / image signing, retention
policy for untagged manifests, and CMK encryption.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


def _policy_enabled(policies: dict, policy_name: str) -> tuple[bool, str | None]:
    """Return (is_enabled, status_value) for a given ACR policy."""
    policy = policies.get(policy_name) or {}
    if not isinstance(policy, dict):
        return False, None
    status_value = policy.get("status")
    is_enabled = isinstance(status_value, str) and status_value.lower() == "enabled"
    return is_enabled, status_value


@check("microsoft.containerregistry/registries", "CIS-AZ-135")
def check_anonymous_pull_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-135: ACR should have anonymous pull disabled."""
    props = asset.raw_properties or {}
    anon_enabled = bool(props.get("anonymousPullEnabled", False))
    return EvalResult(
        status="pass" if not anon_enabled else "fail",
        evidence={"anonymousPullEnabled": anon_enabled},
        description=(
            "Anonymous pull is disabled"
            if not anon_enabled
            else (
                "Anonymous pull is ENABLED — anyone on the internet can pull images from "
                "this registry without authentication. Disable unless serving public images."
            )
        ),
    )


@check("microsoft.containerregistry/registries", "CIS-AZ-136")
def check_network_rule_default_deny(asset: Asset) -> EvalResult:
    """CIS-AZ-136: ACR network rule set should default to Deny."""
    props = asset.raw_properties or {}
    network_rule_set = props.get("networkRuleSet") or {}
    if not isinstance(network_rule_set, dict):
        network_rule_set = {}
    default_action = (network_rule_set.get("defaultAction") or "").lower()
    # If publicNetworkAccess is Disabled the network rule set is not in effect,
    # but the registry is fully locked down, which is the intended secure state.
    public_access = (props.get("publicNetworkAccess") or "").lower()
    if public_access == "disabled":
        return EvalResult(
            status="pass",
            evidence={"publicNetworkAccess": props.get("publicNetworkAccess")},
            description="Public network access is disabled — network rule set not required",
        )
    is_deny = default_action == "deny"
    return EvalResult(
        status="pass" if is_deny else "fail",
        evidence={
            "networkRuleSet.defaultAction": network_rule_set.get("defaultAction"),
            "publicNetworkAccess": props.get("publicNetworkAccess"),
        },
        description=(
            "Network rule set defaults to Deny — only allow-listed IPs and VNets can reach the registry"
            if is_deny
            else (
                f"Network rule set default action is '{default_action or 'Allow (default)'}' — "
                "set to 'Deny' so that only explicitly allow-listed traffic can reach the registry"
            )
        ),
    )


@check("microsoft.containerregistry/registries", "CIS-AZ-137")
def check_quarantine_policy_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-137: ACR quarantine policy should be enabled."""
    props = asset.raw_properties or {}
    policies = props.get("policies") or {}
    if not isinstance(policies, dict):
        policies = {}
    enabled, status_value = _policy_enabled(policies, "quarantinePolicy")
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"quarantinePolicy.status": status_value},
        description=(
            "Quarantine policy is enabled — new images must pass vulnerability scan before being pullable"
            if enabled
            else (
                "Quarantine policy is NOT enabled — images become available immediately after push, "
                "without waiting for the scanner. Enable it so that unscanned images cannot be deployed."
            )
        ),
    )


@check("microsoft.containerregistry/registries", "CIS-AZ-138")
def check_content_trust_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-138: ACR content trust (image signing) should be enabled."""
    props = asset.raw_properties or {}
    policies = props.get("policies") or {}
    if not isinstance(policies, dict):
        policies = {}
    enabled, status_value = _policy_enabled(policies, "trustPolicy")
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"trustPolicy.status": status_value},
        description=(
            "Content trust (image signing) is enabled — only signed images can be pulled"
            if enabled
            else (
                "Content trust is NOT enabled — unsigned images can be pushed and pulled. "
                "Enable the trust policy so that image signatures are verified, preventing "
                "supply-chain tampering."
            )
        ),
    )


@check("microsoft.containerregistry/registries", "CIS-AZ-139")
def check_retention_policy_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-139: ACR retention policy should be enabled to clean up untagged manifests."""
    props = asset.raw_properties or {}
    policies = props.get("policies") or {}
    if not isinstance(policies, dict):
        policies = {}
    enabled, status_value = _policy_enabled(policies, "retentionPolicy")
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"retentionPolicy.status": status_value},
        description=(
            "Retention policy is enabled — untagged manifests are garbage collected automatically"
            if enabled
            else (
                "Retention policy is NOT enabled — untagged manifests accumulate forever, "
                "inflating cost and keeping vulnerable layers around. Enable it to auto-expire "
                "untagged manifests after a fixed number of days."
            )
        ),
    )


@check("microsoft.containerregistry/registries", "CIS-AZ-140")
def check_acr_cmk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-140: ACR should use customer-managed key encryption."""
    props = asset.raw_properties or {}
    encryption = props.get("encryption") or {}
    if not isinstance(encryption, dict):
        encryption = {}
    status_value = (encryption.get("status") or "").lower()
    kv_props = encryption.get("keyVaultProperties") or {}
    if not isinstance(kv_props, dict):
        kv_props = {}
    has_cmk = status_value == "enabled" and bool(kv_props.get("keyIdentifier"))
    return EvalResult(
        status="pass" if has_cmk else "fail",
        evidence={
            "encryption.status": encryption.get("status"),
            "keyIdentifier": "present" if kv_props.get("keyIdentifier") else None,
        },
        description=(
            "Registry uses customer-managed key encryption"
            if has_cmk
            else (
                "Registry does NOT use customer-managed key encryption — images are "
                "encrypted only with the Microsoft-managed key. Enable CMK so that "
                "key rotation and revocation are under your control."
            )
        ),
    )
