"""Unit tests for Web App checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.webapp import (
    check_ftp_disabled,
    check_https_only,
    check_managed_identity,
    check_min_tls_version,
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
