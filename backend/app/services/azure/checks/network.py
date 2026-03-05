"""Network resource checks (CIS-AZ-45, 46, 47, 48)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.network/publicipaddresses", "CIS-AZ-45")
def check_public_ip_ddos(asset: Asset) -> EvalResult:
    """CIS-AZ-45: Public IP should have DDoS protection."""
    props = asset.raw_properties or {}
    ddos = props.get("ddosSettings", {})
    mode = ddos.get("protectionMode", "") if isinstance(ddos, dict) else ""
    # Also check for older property format
    protected = props.get("ddosProtectionPlanEnabled", False)
    is_protected = str(mode).lower() == "enabled" or protected
    return EvalResult(
        status="pass" if is_protected else "fail",
        evidence={"ddosSettings.protectionMode": mode, "ddosProtectionPlanEnabled": protected},
        description="DDoS protection is enabled for this public IP"
        if is_protected
        else "DDoS protection is NOT enabled — enable DDoS Protection Standard",
    )


@check("microsoft.network/virtualnetworks", "CIS-AZ-46")
def check_vnet_ddos(asset: Asset) -> EvalResult:
    """CIS-AZ-46: VNet should have DDoS protection plan enabled."""
    props = asset.raw_properties or {}
    enabled = props.get("enableDdosProtection", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"enableDdosProtection": enabled},
        description="DDoS protection plan is enabled on this VNet"
        if enabled
        else "DDoS protection is NOT enabled — attach a DDoS Protection Standard plan",
    )


@check("microsoft.network/networkwatchers", "CIS-AZ-47")
def check_network_watcher_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-47: Network Watcher should be enabled in all regions."""
    props = asset.raw_properties or {}
    state = props.get("provisioningState", "")
    is_ok = str(state).lower() == "succeeded"
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"provisioningState": state},
        description="Network Watcher is provisioned and enabled"
        if is_ok
        else f"Network Watcher provisioning state is '{state}' — should be Succeeded",
    )


@check("microsoft.network/virtualnetworkgateways", "CIS-AZ-48")
def check_vpn_gateway_sku(asset: Asset) -> EvalResult:
    """CIS-AZ-48: VPN Gateway should not use Basic SKU."""
    props = asset.raw_properties or {}
    sku = props.get("sku", {})
    sku_name = sku.get("name", "") if isinstance(sku, dict) else ""
    is_basic = str(sku_name).lower() == "basic"
    return EvalResult(
        status="fail" if is_basic else "pass",
        evidence={"sku.name": sku_name},
        description=f"VPN Gateway uses '{sku_name}' SKU — upgrade from Basic for better security"
        if is_basic
        else f"VPN Gateway uses '{sku_name}' SKU",
    )
