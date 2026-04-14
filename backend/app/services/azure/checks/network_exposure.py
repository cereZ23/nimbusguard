"""Public-exposure network checks (CIS-AZ-122..127).

Complements the existing SSH/RDP NSG checks (CIS-AZ-13/14) and covers the
other classes of resources attackers probe most often: management ports,
database ports, full-wildcard rules, orphan / Basic-SKU public IPs, and
Azure Firewall threat-intelligence state.

All data is read from properties already collected by the generic Resource
Graph inventory query — no new collector work required.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# Ports attackers probe for lateral movement / data exfiltration.
# SMB (445) and NetBIOS (139) should never be reachable from the internet.
# WinRM (5985/5986) and SSH/RDP lookalikes (22/3389 already covered) enable
# remote code execution if exposed.
_MANAGEMENT_PORTS: dict[int, str] = {
    139: "NetBIOS",
    445: "SMB",
    5985: "WinRM HTTP",
    5986: "WinRM HTTPS",
}

# Database ports commonly attacked when exposed directly.
_DATABASE_PORTS: dict[int, str] = {
    1433: "SQL Server",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    27017: "MongoDB",
    9200: "Elasticsearch",
    5984: "CouchDB",
}

# Source address prefixes that mean "the public internet".
_ANY_SOURCE = {"*", "0.0.0.0/0", "internet", "any"}


def _iter_inbound_allow_rules(asset: Asset):
    """Yield inbound-allow rules from the NSG asset with normalised fields."""
    props = asset.raw_properties or {}
    rules = props.get("securityRules") or []
    if not isinstance(rules, list):
        return
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_props = rule.get("properties", rule)
        if not isinstance(rule_props, dict):
            continue
        direction = str(rule_props.get("direction", "")).lower()
        access = str(rule_props.get("access", "")).lower()
        if direction != "inbound" or access != "allow":
            continue
        source = str(rule_props.get("sourceAddressPrefix", "")).lower()
        dest_port = str(rule_props.get("destinationPortRange", ""))
        dest_port_ranges = rule_props.get("destinationPortRanges") or []
        if not isinstance(dest_port_ranges, list):
            dest_port_ranges = []
        yield {
            "name": rule_props.get("name", rule.get("name", "unknown")),
            "source": source,
            "destinationPortRange": dest_port,
            "destinationPortRanges": [str(p) for p in dest_port_ranges],
        }


def _rule_covers_port(rule: dict, port: int) -> bool:
    """Return True if the rule's destination port range includes ``port``."""
    port_str = str(port)
    single = rule["destinationPortRange"]
    if single == port_str or single == "*":
        return True
    for pr in rule["destinationPortRanges"]:
        if pr == port_str or pr == "*":
            return True
        # Port range like "1000-2000"
        if "-" in pr:
            try:
                low, high = [int(x) for x in pr.split("-", 1)]
            except ValueError:
                continue
            if low <= port <= high:
                return True
    return False


def _find_exposed_ports(asset: Asset, ports: dict[int, str]) -> tuple[list[dict], list[dict]]:
    """Return (exposed_hits, all_rules_inspected) where exposed_hits is a list
    of ``{port, service, rule}`` dicts for rules that expose a sensitive port
    to the public internet."""
    hits: list[dict] = []
    inspected: list[dict] = []
    for rule in _iter_inbound_allow_rules(asset):
        inspected.append(rule)
        if rule["source"] not in _ANY_SOURCE:
            continue
        for port, service in ports.items():
            if _rule_covers_port(rule, port):
                hits.append({"port": port, "service": service, "rule": rule["name"]})
    return hits, inspected


# ── NSG: management ports exposed ──────────────────────────────────


@check("microsoft.network/networksecuritygroups", "CIS-AZ-122")
def check_management_ports_not_exposed(asset: Asset) -> EvalResult:
    """CIS-AZ-122: NSG should not expose SMB / NetBIOS / WinRM to the internet."""
    hits, _ = _find_exposed_ports(asset, _MANAGEMENT_PORTS)
    if not hits:
        return EvalResult(
            status="pass",
            evidence={"management_ports_exposed": []},
            description="No inbound rule exposes SMB, NetBIOS or WinRM from the internet",
        )
    exposed_summary = ", ".join(f"{h['service']} ({h['port']})" for h in hits)
    return EvalResult(
        status="fail",
        evidence={"management_ports_exposed": hits},
        description=(
            f"Management ports are open to the internet: {exposed_summary}. "
            "These protocols must never be reachable from 0.0.0.0/0 — use "
            "Bastion, VPN or Private Link instead."
        ),
    )


# ── NSG: database ports exposed ────────────────────────────────────


@check("microsoft.network/networksecuritygroups", "CIS-AZ-123")
def check_database_ports_not_exposed(asset: Asset) -> EvalResult:
    """CIS-AZ-123: NSG should not expose database management ports to the internet."""
    hits, _ = _find_exposed_ports(asset, _DATABASE_PORTS)
    if not hits:
        return EvalResult(
            status="pass",
            evidence={"database_ports_exposed": []},
            description="No inbound rule exposes database ports from the internet",
        )
    exposed_summary = ", ".join(f"{h['service']} ({h['port']})" for h in hits)
    return EvalResult(
        status="fail",
        evidence={"database_ports_exposed": hits},
        description=(
            f"Database ports are open to the internet: {exposed_summary}. "
            "Databases must be reachable only via private endpoint or VNet "
            "service endpoint, never directly from 0.0.0.0/0."
        ),
    )


# ── NSG: wildcard / any-port rule from the internet ────────────────


@check("microsoft.network/networksecuritygroups", "CIS-AZ-124")
def check_no_wildcard_any_port_rule(asset: Asset) -> EvalResult:
    """CIS-AZ-124: NSG should not have a rule that allows any port from the internet."""
    wildcard_rules: list[dict] = []
    for rule in _iter_inbound_allow_rules(asset):
        if rule["source"] not in _ANY_SOURCE:
            continue
        # A rule is "any port" if the single port or any range entry is "*".
        if rule["destinationPortRange"] == "*" or "*" in rule["destinationPortRanges"]:
            wildcard_rules.append(rule["name"])
    if not wildcard_rules:
        return EvalResult(
            status="pass",
            evidence={"wildcard_rules": []},
            description="No inbound rule allows all ports from the public internet",
        )
    return EvalResult(
        status="fail",
        evidence={"wildcard_rules": wildcard_rules},
        description=(
            f"NSG has rule(s) allowing all ports from the public internet: {wildcard_rules}. "
            "This is effectively 'no firewall' — replace with explicit per-port rules."
        ),
    )


# ── Public IP: Basic SKU is deprecated ─────────────────────────────


@check("microsoft.network/publicipaddresses", "CIS-AZ-125")
def check_public_ip_standard_sku(asset: Asset) -> EvalResult:
    """CIS-AZ-125: Public IP should use Standard SKU (Basic is deprecated/insecure)."""
    props = asset.raw_properties or {}
    sku = props.get("sku") or {}
    sku_name = sku.get("name", "") if isinstance(sku, dict) else ""
    is_standard = str(sku_name).lower() == "standard"
    return EvalResult(
        status="pass" if is_standard else "fail",
        evidence={"sku.name": sku_name or None},
        description=(
            "Public IP uses Standard SKU"
            if is_standard
            else (
                f"Public IP uses '{sku_name or 'unset'}' SKU — Basic is deprecated "
                "(retirement Sept 2025) and lacks availability zones, DDoS Standard "
                "integration and private endpoint support. Recreate with Standard SKU."
            )
        ),
    )


# ── Public IP: orphan (not attached to any resource) ──────────────


@check("microsoft.network/publicipaddresses", "CIS-AZ-126")
def check_public_ip_not_orphan(asset: Asset) -> EvalResult:
    """CIS-AZ-126: Public IP should be attached to a resource (no orphans)."""
    props = asset.raw_properties or {}
    ip_config = props.get("ipConfiguration")
    nat_gateway = props.get("natGateway")
    # Either ipConfiguration (VM NIC, LB frontend, App Gateway...) or natGateway
    # being present means the IP is bound to a resource.
    is_attached = ip_config is not None or nat_gateway is not None
    return EvalResult(
        status="pass" if is_attached else "fail",
        evidence={
            "ipConfiguration": "present" if ip_config else None,
            "natGateway": "present" if nat_gateway else None,
        },
        description=(
            "Public IP is attached to a resource"
            if is_attached
            else (
                "Public IP is orphaned (no ipConfiguration, no natGateway) — "
                "orphan public IPs waste budget and can be reused by attackers "
                "for IP hijacking. Delete or attach to a resource."
            )
        ),
    )


# ── Azure Firewall: threat intelligence in Deny mode ──────────────


@check("microsoft.network/azurefirewalls", "CIS-AZ-127")
def check_firewall_threat_intel_deny(asset: Asset) -> EvalResult:
    """CIS-AZ-127: Azure Firewall threat intelligence should be in Deny mode."""
    props = asset.raw_properties or {}
    # threatIntelMode lives either at the top of firewall properties or inside
    # additionalProperties depending on the API version.
    mode = (
        props.get("threatIntelMode")
        or (props.get("additionalProperties") or {}).get("ThreatIntel.Whitelist.IpAddresses")
        or ""
    )
    mode_str = str(mode).lower() if mode else ""
    is_deny = mode_str == "deny"
    return EvalResult(
        status="pass" if is_deny else "fail",
        evidence={"threatIntelMode": mode or None},
        description=(
            "Azure Firewall threat intelligence is in Deny mode"
            if is_deny
            else (
                f"Azure Firewall threat intelligence mode is '{mode or 'not set'}' — "
                "set it to 'Deny' so known-malicious traffic is blocked, not just logged"
            )
        ),
    )
