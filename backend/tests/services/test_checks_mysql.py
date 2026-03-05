"""Unit tests for MySQL checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.mysql import check_min_tls_version, check_public_access, check_ssl_enforcement


def _make_asset(resource_type="microsoft.dbformysql/flexibleservers", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testmysql",
        resource_type=resource_type,
        name="test-mysql",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckSslEnforcement:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"sslEnforcement": "Enabled"})
        assert check_ssl_enforcement(asset).status == "pass"

    def test_pass_when_secure_transport(self):
        asset = _make_asset(raw_properties={"requireSecureTransport": "ON"})
        assert check_ssl_enforcement(asset).status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"sslEnforcement": "Disabled"})
        assert check_ssl_enforcement(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_ssl_enforcement(asset).status == "fail"


class TestCheckPublicAccess:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Disabled"})
        assert check_public_access(asset).status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Enabled"})
        assert check_public_access(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_public_access(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_public_access(asset).status == "fail"


class TestCheckMinTlsVersion:
    def test_pass_when_tls_12(self):
        asset = _make_asset(raw_properties={"minimalTlsVersion": "TLSv1.2"})
        assert check_min_tls_version(asset).status == "pass"

    def test_fail_when_tls_10(self):
        asset = _make_asset(raw_properties={"minimalTlsVersion": "TLSv1.0"})
        assert check_min_tls_version(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_min_tls_version(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_min_tls_version(asset).status == "fail"
