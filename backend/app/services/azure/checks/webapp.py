"""Web App / App Service checks (CIS-AZ-10, 23, 24, 25, 26, 67, 68, 69, 70, 71)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.web/sites", "CIS-AZ-10")
def check_https_only(asset: Asset) -> EvalResult:
    """CIS-AZ-10: Web applications should only be accessible over HTTPS."""
    props = asset.raw_properties or {}
    https_only = props.get("httpsOnly", False)
    return EvalResult(
        status="pass" if https_only else "fail",
        evidence={"httpsOnly": https_only},
        description="HTTPS Only is enabled"
        if https_only
        else "HTTPS Only is NOT enabled — HTTP traffic is allowed",
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
        description="HTTP/2 is enabled"
        if http2
        else "HTTP/2 is NOT enabled — enable for better performance",
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
