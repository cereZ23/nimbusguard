"""Network Interface checks (CIS-AZ-65, 66)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.network/networkinterfaces", "CIS-AZ-65")
def check_no_public_ip(asset: Asset) -> EvalResult:
    """CIS-AZ-65: NICs should not have public IPs directly attached."""
    props = asset.raw_properties or {}
    ip_configs = props.get("ipConfigurations", [])
    has_public = False
    if isinstance(ip_configs, list):
        for config in ip_configs:
            config_props = config.get("properties", config)
            public_ip = config_props.get("publicIPAddress")
            if public_ip is not None:
                has_public = True
                break
    return EvalResult(
        status="fail" if has_public else "pass",
        evidence={"hasPublicIP": has_public},
        description="NIC has a public IP attached — consider using a load balancer or NAT gateway"
        if has_public
        else "No public IP directly attached to NIC",
    )


@check("microsoft.network/networkinterfaces", "CIS-AZ-66")
def check_ip_forwarding_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-66: IP forwarding should be disabled unless required (e.g. NVA)."""
    props = asset.raw_properties or {}
    ip_forwarding = props.get("enableIPForwarding", False)
    return EvalResult(
        status="fail" if ip_forwarding else "pass",
        evidence={"enableIPForwarding": ip_forwarding},
        description="IP forwarding is ENABLED — verify this NIC is used for a network virtual appliance"
        if ip_forwarding
        else "IP forwarding is disabled",
    )
