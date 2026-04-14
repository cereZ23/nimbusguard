"""Web App / App Service checks (CIS-AZ-10, 23, 24, 25, 26, 67, 68, 69, 70, 71, 89..94)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# TLS cipher suites considered strong (modern AEAD ciphers).
# Accepted values that pass the minTlsCipherSuite control.
_STRONG_TLS_CIPHERS = {
    "TLS_AES_128_GCM_SHA256",
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
}


@check("microsoft.web/sites", "CIS-AZ-10")
def check_https_only(asset: Asset) -> EvalResult:
    """CIS-AZ-10: Web applications should only be accessible over HTTPS."""
    props = asset.raw_properties or {}
    https_only = props.get("httpsOnly", False)
    return EvalResult(
        status="pass" if https_only else "fail",
        evidence={"httpsOnly": https_only},
        description="HTTPS Only is enabled" if https_only else "HTTPS Only is NOT enabled — HTTP traffic is allowed",
    )


@check("microsoft.web/sites", "CIS-AZ-23")
def check_min_tls_version(asset: Asset) -> EvalResult:
    """CIS-AZ-23: Web apps should require minimum TLS 1.2."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig", {})
    tls_version = site_config.get("minTlsVersion", "")
    is_ok = tls_version >= "1.2" if tls_version else False
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"siteConfig.minTlsVersion": tls_version},
        description="Minimum TLS version is 1.2 or higher"
        if is_ok
        else f"Minimum TLS version is {tls_version or 'not set'} — should be at least 1.2",
    )


@check("microsoft.web/sites", "CIS-AZ-24")
def check_remote_debugging_off(asset: Asset) -> EvalResult:
    """CIS-AZ-24: Remote debugging should be turned off for web apps."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig", {})
    remote_debug = site_config.get("remoteDebuggingEnabled", False)
    return EvalResult(
        status="pass" if not remote_debug else "fail",
        evidence={"siteConfig.remoteDebuggingEnabled": remote_debug},
        description="Remote debugging is disabled"
        if not remote_debug
        else "Remote debugging is ENABLED — disable in production",
    )


@check("microsoft.web/sites", "CIS-AZ-25")
def check_ftp_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-25: FTP should be disabled or FTPS only on web apps."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig", {})
    ftps_state = site_config.get("ftpsState", "AllAllowed")
    is_ok = ftps_state in ("Disabled", "FtpsOnly")
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"siteConfig.ftpsState": ftps_state},
        description=f"FTP state is '{ftps_state}'"
        if is_ok
        else f"FTP state is '{ftps_state}' — should be 'Disabled' or 'FtpsOnly'",
    )


@check("microsoft.web/sites", "CIS-AZ-26")
def check_managed_identity(asset: Asset) -> EvalResult:
    """CIS-AZ-26: Web apps should use managed identity."""
    props = asset.raw_properties or {}
    identity = props.get("identity", {})
    identity_type = identity.get("type") if isinstance(identity, dict) else None
    has_identity = identity_type is not None and identity_type.lower() != "none"
    return EvalResult(
        status="pass" if has_identity else "fail",
        evidence={"identity.type": identity_type},
        description=f"Managed identity is configured ({identity_type})"
        if has_identity
        else "No managed identity configured — use managed identity instead of credentials",
    )


@check("microsoft.web/sites", "CIS-AZ-67")
def check_client_cert_auth(asset: Asset) -> EvalResult:
    """CIS-AZ-67: Web app should require client certificate authentication."""
    props = asset.raw_properties or {}
    client_cert = props.get("clientCertEnabled", False)
    return EvalResult(
        status="pass" if client_cert else "fail",
        evidence={"clientCertEnabled": client_cert},
        description="Client certificate authentication is enabled"
        if client_cert
        else "Client certificate authentication is NOT enabled",
    )


@check("microsoft.web/sites", "CIS-AZ-68")
def check_always_on(asset: Asset) -> EvalResult:
    """CIS-AZ-68: Web app should have Always On enabled."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig", {})
    always_on = site_config.get("alwaysOn", False) if isinstance(site_config, dict) else False
    return EvalResult(
        status="pass" if always_on else "fail",
        evidence={"siteConfig.alwaysOn": always_on},
        description="Always On is enabled"
        if always_on
        else "Always On is NOT enabled — app may experience cold starts",
    )


@check("microsoft.web/sites", "CIS-AZ-69")
def check_http2_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-69: Web app should have HTTP/2 enabled."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig", {})
    http2 = site_config.get("http20Enabled", False) if isinstance(site_config, dict) else False
    return EvalResult(
        status="pass" if http2 else "fail",
        evidence={"siteConfig.http20Enabled": http2},
        description="HTTP/2 is enabled" if http2 else "HTTP/2 is NOT enabled — enable for better performance",
    )


@check("microsoft.web/sites", "CIS-AZ-70")
def check_vnet_integration(asset: Asset) -> EvalResult:
    """CIS-AZ-70: Web app should have VNet integration configured."""
    props = asset.raw_properties or {}
    vnet_info = props.get("virtualNetworkSubnetId")
    site_config = props.get("siteConfig", {})
    vnet_route = site_config.get("vnetRouteAllEnabled", False) if isinstance(site_config, dict) else False
    has_vnet = vnet_info is not None or vnet_route
    return EvalResult(
        status="pass" if has_vnet else "fail",
        evidence={"virtualNetworkSubnetId": vnet_info, "vnetRouteAllEnabled": vnet_route},
        description="VNet integration is configured"
        if has_vnet
        else "No VNet integration — outbound traffic goes through public internet",
    )


@check("microsoft.web/sites", "CIS-AZ-71")
def check_auth_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-71: Web app should have authentication configured."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig", {})
    auth_settings = props.get("authSettings") or props.get("siteAuthSettings")
    # Check EasyAuth / Authentication v2
    auth_enabled = False
    if isinstance(auth_settings, dict):
        auth_enabled = auth_settings.get("enabled", False)
    # Alternative: check siteConfig for auth
    if not auth_enabled and isinstance(site_config, dict):
        auth_enabled = site_config.get("siteAuthEnabled", False)
    return EvalResult(
        status="pass" if auth_enabled else "fail",
        evidence={"authSettingsEnabled": auth_enabled},
        description="Authentication is configured on the web app"
        if auth_enabled
        else "Authentication is NOT configured — consider enabling App Service Authentication",
    )


@check("microsoft.web/sites", "CIS-AZ-89")
def check_cors_restrictive(asset: Asset) -> EvalResult:
    """CIS-AZ-89: Web app CORS should not allow wildcard origins."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig") or {}
    cors = site_config.get("cors") if isinstance(site_config, dict) else None
    # cors is None or empty → no CORS configured, not a fail (CORS not in use)
    if not isinstance(cors, dict):
        return EvalResult(
            status="pass",
            evidence={"cors": None},
            description="CORS is not configured — no cross-origin access allowed",
        )
    allowed_origins = cors.get("allowedOrigins") or []
    if not isinstance(allowed_origins, list):
        allowed_origins = []
    has_wildcard = "*" in allowed_origins
    return EvalResult(
        status="fail" if has_wildcard else "pass",
        evidence={"cors.allowedOrigins": allowed_origins},
        description=(f"CORS allows wildcard origin '*' — any site can call the API. Allowed origins: {allowed_origins}")
        if has_wildcard
        else f"CORS origins are explicit (no wildcard): {allowed_origins or 'none'}",
    )


@check("microsoft.web/sites", "CIS-AZ-90")
def check_health_check_path(asset: Asset) -> EvalResult:
    """CIS-AZ-90: Web app should have a health check path configured."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig") or {}
    health_path = site_config.get("healthCheckPath") if isinstance(site_config, dict) else None
    has_path = bool(health_path)
    return EvalResult(
        status="pass" if has_path else "fail",
        evidence={"siteConfig.healthCheckPath": health_path},
        description=f"Health check path is configured: {health_path}"
        if has_path
        else "Health check path is NOT configured — unhealthy instances cannot be auto-removed",
    )


@check("microsoft.web/sites", "CIS-AZ-91")
def check_auto_heal_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-91: Web app should have auto-heal enabled for automatic recovery."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig") or {}
    auto_heal = site_config.get("autoHealEnabled") if isinstance(site_config, dict) else None
    is_enabled = bool(auto_heal)
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"siteConfig.autoHealEnabled": auto_heal},
        description="Auto-heal is enabled"
        if is_enabled
        else "Auto-heal is NOT enabled — stuck instances will not recover automatically",
    )


@check("microsoft.web/sites", "CIS-AZ-92")
def check_min_tls_cipher_suite(asset: Asset) -> EvalResult:
    """CIS-AZ-92: Web app should enforce a strong minimum TLS cipher suite."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig") or {}
    min_cipher = site_config.get("minTlsCipherSuite") if isinstance(site_config, dict) else None
    if not min_cipher:
        return EvalResult(
            status="fail",
            evidence={"siteConfig.minTlsCipherSuite": None},
            description="Minimum TLS cipher suite is NOT configured — weak ciphers may be accepted",
        )
    is_strong = min_cipher in _STRONG_TLS_CIPHERS
    return EvalResult(
        status="pass" if is_strong else "fail",
        evidence={"siteConfig.minTlsCipherSuite": min_cipher},
        description=f"Minimum TLS cipher suite is strong: {min_cipher}"
        if is_strong
        else (
            f"Minimum TLS cipher suite '{min_cipher}' is weak — use a modern AEAD cipher (e.g. TLS_AES_128_GCM_SHA256)"
        ),
    )


@check("microsoft.web/sites", "CIS-AZ-93")
def check_public_network_access_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-93: Web app should disable public network access when private endpoint is in use."""
    props = asset.raw_properties or {}
    public_access = (props.get("publicNetworkAccess") or "").lower()
    private_endpoints = props.get("privateEndpointConnections") or []
    # If there are private endpoints, public access SHOULD be disabled.
    # If there are no private endpoints, public access is expected (pass).
    has_private = bool(private_endpoints)
    if not has_private:
        # No private endpoint → public exposure is by design, skip as pass.
        return EvalResult(
            status="pass",
            evidence={
                "publicNetworkAccess": props.get("publicNetworkAccess"),
                "privateEndpointConnections": len(private_endpoints),
            },
            description=("No private endpoint configured — public network access is the only ingress path"),
        )
    is_disabled = public_access in ("disabled", "")
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={
            "publicNetworkAccess": props.get("publicNetworkAccess"),
            "privateEndpointConnections": len(private_endpoints),
        },
        description=(
            f"Public network access is '{props.get('publicNetworkAccess')}' despite "
            f"{len(private_endpoints)} private endpoint(s) — traffic can still reach the app from the internet"
        )
        if not is_disabled
        else "Public network access is disabled; traffic is routed via private endpoint only",
    )


@check("microsoft.web/sites", "CIS-AZ-94")
def check_ip_restrictions(asset: Asset) -> EvalResult:
    """CIS-AZ-94: Web app should have IP security restrictions with a default-deny policy."""
    props = asset.raw_properties or {}
    site_config = props.get("siteConfig") or {}
    if not isinstance(site_config, dict):
        site_config = {}
    restrictions = site_config.get("ipSecurityRestrictions") or []
    default_action = (site_config.get("ipSecurityRestrictionsDefaultAction") or "").lower()
    # Pass conditions:
    # 1. Default action is explicitly "deny", OR
    # 2. There is at least one explicit restriction (non-default).
    has_default_deny = default_action == "deny"
    # Filter out the implicit "allow all" rule present on every web app.
    non_default_rules = [
        r
        for r in restrictions
        if isinstance(r, dict) and (r.get("name") or "").lower() not in ("allow all", "deny all")
    ]
    is_restricted = has_default_deny or len(non_default_rules) > 0
    return EvalResult(
        status="pass" if is_restricted else "fail",
        evidence={
            "ipSecurityRestrictionsDefaultAction": site_config.get("ipSecurityRestrictionsDefaultAction"),
            "ipSecurityRestrictions_count": len(non_default_rules),
        },
        description=(
            f"IP restrictions configured (default action: {default_action or 'none'}, "
            f"{len(non_default_rules)} explicit rule(s))"
        )
        if is_restricted
        else "No IP restrictions configured — web app is reachable from any source IP",
    )
