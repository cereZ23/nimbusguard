"""Front Door checks (CIS-AZ-49, 50)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.network/frontdoors", "CIS-AZ-49")
def check_waf_policy(asset: Asset) -> EvalResult:
    """CIS-AZ-49: Front Door should have a WAF policy attached."""
    props = asset.raw_properties or {}
    frontend_endpoints = props.get("frontendEndpoints", [])
    has_waf = False
    if isinstance(frontend_endpoints, list):
        for endpoint in frontend_endpoints:
            ep_props = endpoint.get("properties", endpoint)
            waf = ep_props.get("webApplicationFirewallPolicyLink")
            if waf is not None:
                has_waf = True
                break
    return EvalResult(
        status="pass" if has_waf else "fail",
        evidence={"wafPolicyAttached": has_waf},
        description="WAF policy is attached to Front Door endpoints"
        if has_waf
        else "No WAF policy attached — enable WAF on Front Door for L7 protection",
    )


@check("microsoft.network/frontdoors", "CIS-AZ-50")
def check_https_redirect(asset: Asset) -> EvalResult:
    """CIS-AZ-50: Front Door should redirect HTTP to HTTPS."""
    props = asset.raw_properties or {}
    routing_rules = props.get("routingRules", [])
    has_redirect = False
    if isinstance(routing_rules, list):
        for rule in routing_rules:
            rule_props = rule.get("properties", rule)
            redirect = rule_props.get("routeConfiguration", {})
            if isinstance(redirect, dict):
                rtype = redirect.get("@odata.type", "")
                if "redirect" in str(rtype).lower():
                    protocol = redirect.get("redirectProtocol", "")
                    if str(protocol).lower() == "httpsonly":
                        has_redirect = True
                        break
    return EvalResult(
        status="pass" if has_redirect else "fail",
        evidence={"httpsRedirectConfigured": has_redirect},
        description="HTTP to HTTPS redirect is configured"
        if has_redirect
        else "HTTP to HTTPS redirect is NOT configured — add redirect routing rule",
    )
