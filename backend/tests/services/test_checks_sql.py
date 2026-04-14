"""Unit tests for SQL Server/Database checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.sql import (
    check_aad_admin,
    check_auditing,
    check_min_tls_version,
    check_public_network_access,
    check_tde_enabled,
)


def _make_asset(
    resource_type: str = "microsoft.sql/servers",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testsql",
        resource_type=resource_type,
        name="test-sql",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckTdeEnabled:
    def test_pass_when_enabled(self):
        asset = _make_asset(
            resource_type="microsoft.sql/servers/databases",
            raw_properties={"transparentDataEncryption": {"status": "Enabled"}},
        )
        result = check_tde_enabled(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(
            resource_type="microsoft.sql/servers/databases",
            raw_properties={"transparentDataEncryption": {"status": "Disabled"}},
        )
        result = check_tde_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(resource_type="microsoft.sql/servers/databases", raw_properties={})
        result = check_tde_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(resource_type="microsoft.sql/servers/databases", raw_properties=None)
        result = check_tde_enabled(asset)
        assert result.status == "fail"


class TestCheckPublicNetworkAccess:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Disabled"})
        result = check_public_network_access(asset)
        assert result.status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Enabled"})
        result = check_public_network_access(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_public_network_access(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_public_network_access(asset)
        assert result.status == "fail"


class TestCheckMinTlsVersion:
    def test_pass_when_tls_12(self):
        asset = _make_asset(raw_properties={"minimalTlsVersion": "1.2"})
        result = check_min_tls_version(asset)
        assert result.status == "pass"

    def test_fail_when_tls_10(self):
        asset = _make_asset(raw_properties={"minimalTlsVersion": "1.0"})
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


class TestCheckAadAdmin:
    def test_pass_when_configured(self):
        asset = _make_asset(raw_properties={"administrators": {"login": "admin@test.com"}})
        result = check_aad_admin(asset)
        assert result.status == "pass"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_aad_admin(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_aad_admin(asset)
        assert result.status == "fail"

    def test_fail_when_explicitly_none(self):
        asset = _make_asset(raw_properties={"administrators": None})
        result = check_aad_admin(asset)
        assert result.status == "fail"


class TestCheckAuditing:
    def test_pass_when_settings_present(self):
        asset = _make_asset(raw_properties={"auditingSettings": {"state": "Enabled"}})
        result = check_auditing(asset)
        assert result.status == "pass"

    def test_pass_when_audit_settings_key(self):
        asset = _make_asset(raw_properties={"auditSettings": {"state": "Enabled"}})
        result = check_auditing(asset)
        assert result.status == "pass"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_auditing(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_auditing(asset)
        assert result.status == "fail"
