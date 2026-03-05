"""Network Security Group checks (CIS-AZ-06, 13, 14)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


def _has_dangerous_inbound_rule(asset: Asset, port: int) -> tuple[bool, dict]:
    """Check if any security rule allows inbound access from * on a given port."""
    props = asset.raw_properties or {}
    security_rules = props.get("securityRules", [])

    for rule in security_rules:
        rule_props = rule.get("properties", rule)
        direction = str(rule_props.get("direction", "")).lower()
        access = str(rule_props.get("access", "")).lower()
        source = str(rule_props.get("sourceAddressPrefix", ""))

        if direction != "inbound" or access != "allow":
            continue

        if source not in ("*", "0.0.0.0/0", "internet", "any"):
            continue

        # Check port match
        dest_port = str(rule_props.get("destinationPortRange", ""))
        dest_port_ranges = rule_props.get("destinationPortRanges", [])

        port_str = str(port)
        if dest_port == port_str or dest_port == "*":
            return True, {
                "rule_name": rule_props.get("name", rule.get("name", "unknown")),
                "sourceAddressPrefix": source,
                "destinationPortRange": dest_port,
                "access": access,
                "direction": direction,
            }
        for pr in dest_port_ranges:
            if str(pr) == port_str or str(pr) == "*":
                return True, {
                    "rule_name": rule_props.get("name", rule.get("name", "unknown")),
                    "sourceAddressPrefix": source,
                    "destinationPortRange": pr,
                    "access": access,
                    "direction": direction,
                }

    return False, {}


@check("microsoft.network/networksecuritygroups", "CIS-AZ-13")
def check_ssh_restricted(asset: Asset) -> EvalResult:
    """CIS-AZ-13: Restrict SSH access from internet (port 22)."""
    is_open, rule_evidence = _has_dangerous_inbound_rule(asset, 22)
    return EvalResult(
        status="fail" if is_open else "pass",
        evidence=rule_evidence if is_open else {"ssh_open_from_internet": False},
        description="SSH (port 22) is open from the internet — restrict access"
        if is_open
        else "No inbound rule allows SSH from the internet",
    )


@check("microsoft.network/networksecuritygroups", "CIS-AZ-14")
def check_rdp_restricted(asset: Asset) -> EvalResult:
    """CIS-AZ-14: Restrict RDP access from internet (port 3389)."""
    is_open, rule_evidence = _has_dangerous_inbound_rule(asset, 3389)
    return EvalResult(
        status="fail" if is_open else "pass",
        evidence=rule_evidence if is_open else {"rdp_open_from_internet": False},
        description="RDP (port 3389) is open from the internet — restrict access"
        if is_open
        else "No inbound rule allows RDP from the internet",
    )


@check("microsoft.network/networksecuritygroups", "CIS-AZ-06")
def check_flow_logs(asset: Asset) -> EvalResult:
    """CIS-AZ-06: NSG flow logs should be configured.

    Best-effort: Resource Graph doesn't directly expose flow log configuration.
    """
    props = asset.raw_properties or {}
    flow_logs = props.get("flowLogs")
    if flow_logs is not None:
        return EvalResult(
            status="pass",
            evidence={"flowLogs": "present"},
            description="Flow logs configuration detected in raw properties",
        )
    return EvalResult(
        status="fail",
        evidence={"flowLogs": "not_found_in_resource_graph"},
        description="Flow logs not found in Resource Graph properties "
        "(may require separate API call to verify — best-effort check)",
    )
