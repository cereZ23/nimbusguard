"""Unit tests for Web App checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.webapp import (
    check_auto_heal_enabled,
    check_cors_restrictive,
    check_ftp_disabled,
    check_health_check_path,
    check_https_only,
    check_ip_restrictions,
    check_managed_identity,
    check_min_tls_cipher_suite,
    check_min_tls_version,
    check_public_network_access_disabled,
    check_remote_debugging_off,
)


def _make_asset(
    resource_type: str = "microsoft.web/sites",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testapp",
        resource_type=resource_type,
        name="test-app",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckHttpsOnly:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"httpsOnly": True})
        result = check_https_only(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"httpsOnly": False})
        result = check_https_only(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_https_only(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_https_only(asset)
        assert result.status == "fail"


class TestCheckMinTlsVersion:
    def test_pass_when_tls_12(self):
        asset = _make_asset(raw_properties={"siteConfig": {"minTlsVersion": "1.2"}})
        result = check_min_tls_version(asset)
        assert result.status == "pass"

    def test_pass_when_tls_13(self):
        asset = _make_asset(raw_properties={"siteConfig": {"minTlsVersion": "1.3"}})
        result = check_min_tls_version(asset)
        assert result.status == "pass"

    def test_fail_when_tls_10(self):
        asset = _make_asset(raw_properties={"siteConfig": {"minTlsVersion": "1.0"}})
        result = check_min_tls_version(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_min_tls_version(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_min_tls_version(asset)
        assert result.status == "fail"


class TestCheckRemoteDebuggingOff:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"siteConfig": {"remoteDebuggingEnabled": False}})
        result = check_remote_debugging_off(asset)
        assert result.status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"siteConfig": {"remoteDebuggingEnabled": True}})
        result = check_remote_debugging_off(asset)
        assert result.status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_remote_debugging_off(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_remote_debugging_off(asset)
        assert result.status == "pass"


class TestCheckFtpDisabled:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"siteConfig": {"ftpsState": "Disabled"}})
        result = check_ftp_disabled(asset)
        assert result.status == "pass"

    def test_pass_when_ftps_only(self):
        asset = _make_asset(raw_properties={"siteConfig": {"ftpsState": "FtpsOnly"}})
        result = check_ftp_disabled(asset)
        assert result.status == "pass"

    def test_fail_when_all_allowed(self):
        asset = _make_asset(raw_properties={"siteConfig": {"ftpsState": "AllAllowed"}})
        result = check_ftp_disabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_ftp_disabled(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_ftp_disabled(asset)
        assert result.status == "fail"


class TestCheckManagedIdentity:
    def test_pass_when_system_assigned(self):
        asset = _make_asset(raw_properties={"identity": {"type": "SystemAssigned"}})
        result = check_managed_identity(asset)
        assert result.status == "pass"

    def test_pass_when_user_assigned(self):
        asset = _make_asset(raw_properties={"identity": {"type": "UserAssigned"}})
        result = check_managed_identity(asset)
        assert result.status == "pass"

    def test_fail_when_none_type(self):
        asset = _make_asset(raw_properties={"identity": {"type": "None"}})
        result = check_managed_identity(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_managed_identity(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_managed_identity(asset)
        assert result.status == "fail"


class TestCheckCorsRestrictive:
    def test_pass_when_no_cors_configured(self):
        asset = _make_asset(raw_properties={"siteConfig": {"cors": None}})
        assert check_cors_restrictive(asset).status == "pass"

    def test_pass_when_cors_empty_origins(self):
        asset = _make_asset(raw_properties={"siteConfig": {"cors": {"allowedOrigins": []}}})
        assert check_cors_restrictive(asset).status == "pass"

    def test_pass_when_explicit_origins(self):
        asset = _make_asset(
            raw_properties={
                "siteConfig": {"cors": {"allowedOrigins": ["https://app.example.com", "https://api.example.com"]}}
            }
        )
        assert check_cors_restrictive(asset).status == "pass"

    def test_fail_when_wildcard(self):
        asset = _make_asset(raw_properties={"siteConfig": {"cors": {"allowedOrigins": ["*"]}}})
        assert check_cors_restrictive(asset).status == "fail"

    def test_fail_when_wildcard_mixed(self):
        asset = _make_asset(
            raw_properties={"siteConfig": {"cors": {"allowedOrigins": ["https://app.example.com", "*"]}}}
        )
        assert check_cors_restrictive(asset).status == "fail"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_cors_restrictive(asset).status == "pass"


class TestCheckHealthCheckPath:
    def test_pass_when_path_set(self):
        asset = _make_asset(raw_properties={"siteConfig": {"healthCheckPath": "/healthz"}})
        assert check_health_check_path(asset).status == "pass"

    def test_fail_when_path_empty(self):
        asset = _make_asset(raw_properties={"siteConfig": {"healthCheckPath": ""}})
        assert check_health_check_path(asset).status == "fail"

    def test_fail_when_path_none(self):
        asset = _make_asset(raw_properties={"siteConfig": {"healthCheckPath": None}})
        assert check_health_check_path(asset).status == "fail"

    def test_fail_when_site_config_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_health_check_path(asset).status == "fail"


class TestCheckAutoHealEnabled:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"siteConfig": {"autoHealEnabled": True}})
        assert check_auto_heal_enabled(asset).status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"siteConfig": {"autoHealEnabled": False}})
        assert check_auto_heal_enabled(asset).status == "fail"

    def test_fail_when_none(self):
        asset = _make_asset(raw_properties={"siteConfig": {"autoHealEnabled": None}})
        assert check_auto_heal_enabled(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_auto_heal_enabled(asset).status == "fail"


class TestCheckMinTlsCipherSuite:
    def test_pass_with_strong_cipher(self):
        asset = _make_asset(raw_properties={"siteConfig": {"minTlsCipherSuite": "TLS_AES_128_GCM_SHA256"}})
        assert check_min_tls_cipher_suite(asset).status == "pass"

    def test_pass_with_chacha(self):
        asset = _make_asset(
            raw_properties={"siteConfig": {"minTlsCipherSuite": "TLS_CHACHA20_POLY1305_SHA256"}}
        )
        assert check_min_tls_cipher_suite(asset).status == "pass"

    def test_fail_with_weak_cipher(self):
        asset = _make_asset(
            raw_properties={"siteConfig": {"minTlsCipherSuite": "TLS_RSA_WITH_AES_128_CBC_SHA"}}
        )
        assert check_min_tls_cipher_suite(asset).status == "fail"

    def test_fail_when_not_set(self):
        asset = _make_asset(raw_properties={"siteConfig": {"minTlsCipherSuite": None}})
        assert check_min_tls_cipher_suite(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_min_tls_cipher_suite(asset).status == "fail"


class TestCheckPublicNetworkAccessDisabled:
    def test_pass_when_no_private_endpoint(self):
        # No private endpoint → public access is expected ingress → skip as pass.
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Enabled", "privateEndpointConnections": []})
        assert check_public_network_access_disabled(asset).status == "pass"

    def test_pass_when_private_endpoint_and_disabled(self):
        asset = _make_asset(
            raw_properties={
                "publicNetworkAccess": "Disabled",
                "privateEndpointConnections": [{"id": "pe1"}],
            }
        )
        assert check_public_network_access_disabled(asset).status == "pass"

    def test_fail_when_private_endpoint_and_public_enabled(self):
        asset = _make_asset(
            raw_properties={
                "publicNetworkAccess": "Enabled",
                "privateEndpointConnections": [{"id": "pe1"}],
            }
        )
        assert check_public_network_access_disabled(asset).status == "fail"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_public_network_access_disabled(asset).status == "pass"


class TestCheckIpRestrictions:
    def test_pass_with_default_deny(self):
        asset = _make_asset(
            raw_properties={"siteConfig": {"ipSecurityRestrictionsDefaultAction": "Deny"}}
        )
        assert check_ip_restrictions(asset).status == "pass"

    def test_pass_with_explicit_rule(self):
        asset = _make_asset(
            raw_properties={
                "siteConfig": {
                    "ipSecurityRestrictions": [
                        {"name": "office", "ipAddress": "1.2.3.4/32", "action": "Allow"}
                    ]
                }
            }
        )
        assert check_ip_restrictions(asset).status == "pass"

    def test_fail_with_only_default_allow_rule(self):
        # The implicit "Allow all" rule should not count as a real restriction.
        asset = _make_asset(
            raw_properties={
                "siteConfig": {
                    "ipSecurityRestrictions": [{"name": "Allow all", "action": "Allow"}],
                    "ipSecurityRestrictionsDefaultAction": "Allow",
                }
            }
        )
        assert check_ip_restrictions(asset).status == "fail"

    def test_fail_when_no_restrictions(self):
        asset = _make_asset(raw_properties={"siteConfig": {}})
        assert check_ip_restrictions(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_ip_restrictions(asset).status == "fail"
