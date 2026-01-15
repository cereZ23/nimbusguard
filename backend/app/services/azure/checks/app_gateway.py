"""Application Gateway checks (CIS-AZ-43, 44)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.network/applicationgateways", "CIS-AZ-43")
def check_waf_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-43: Application Gateway should have WAF enabled."""
    props = asset.raw_properties or {}
    waf_config = props.get("webApplicationFirewallConfiguration")
    firewall_policy = props.get("firewallPolicy")
    has_waf = waf_config is not None or firewall_policy is not None
    return EvalResult(
        status="pass" if has_waf else "fail",
        evidence={
            "webApplicationFirewallConfiguration": "present" if waf_config else None,
            "firewallPolicy": "present" if firewall_policy else None,
        },
        description="WAF is enabled on Application Gateway"
        if has_waf
        else "WAF is NOT enabled — enable Web Application Firewall for L7 protection",
    )


@check("microsoft.network/applicationgateways", "CIS-AZ-44")
def check_waf_v2_sku(asset: Asset) -> EvalResult:
    """CIS-AZ-44: Application Gateway should use WAF_v2 SKU."""
    props = asset.raw_properties or {}
    sku = props.get("sku", {})
    tier = sku.get("tier", "") if isinstance(sku, dict) else ""
    is_waf_v2 = str(tier).lower() in ("waf_v2", "wafv2")
    return EvalResult(
        status="pass" if is_waf_v2 else "fail",
        evidence={"sku.tier": tier},
        description="Application Gateway uses WAF_v2 SKU"
        if is_waf_v2
        else f"Application Gateway SKU is '{tier}' — upgrade to WAF_v2 for best protection",
    )
