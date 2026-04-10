"""Unit tests for Log Analytics checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.log_analytics import (
    check_cmk_encryption,
    check_daily_quota_configured,
    check_public_access_ingestion_disabled,
    check_public_access_query_disabled,
    check_resource_permissions_only,
    check_retention_days,
)


def _make_asset(resource_type="microsoft.operationalinsights/workspaces", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testla",
        resource_type=resource_type,
        name="test-la",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckRetentionDays:
    def test_pass_when_90(self):
        asset = _make_asset(raw_properties={"retentionInDays": 90})
        assert check_retention_days(asset).status == "pass"

    def test_pass_when_365(self):
        asset = _make_asset(raw_properties={"retentionInDays": 365})
        assert check_retention_days(asset).status == "pass"

    def test_fail_when_30(self):
        asset = _make_asset(raw_properties={"retentionInDays": 30})
        assert check_retention_days(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_retention_days(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_retention_days(asset).status == "fail"


class TestCheckCmkEncryption:
    def test_pass_when_cluster(self):
        asset = _make_asset(raw_properties={"clusterResourceId": "/sub/cluster1"})
        assert check_cmk_encryption(asset).status == "pass"

    def test_pass_when_key_vault(self):
        asset = _make_asset(
            raw_properties={"encryption": {"keyVaultProperties": {"keyVaultUri": "https://kv.vault.azure.net"}}}
        )
        assert check_cmk_encryption(asset).status == "pass"

    def test_fail_when_no_cmk(self):
        asset = _make_asset(raw_properties={})
        assert check_cmk_encryption(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_cmk_encryption(asset).status == "fail"


class TestCheckDailyQuotaConfigured:
    def test_pass_when_quota_set(self):
        asset = _make_asset(raw_properties={"workspaceCapping": {"dailyQuotaGb": 5.0}})
        assert check_daily_quota_configured(asset).status == "pass"

    def test_fail_when_no_cap_sentinel(self):
        asset = _make_asset(raw_properties={"workspaceCapping": {"dailyQuotaGb": -1.0}})
        assert check_daily_quota_configured(asset).status == "fail"

    def test_fail_when_zero(self):
        asset = _make_asset(raw_properties={"workspaceCapping": {"dailyQuotaGb": 0}})
        assert check_daily_quota_configured(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_daily_quota_configured(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_daily_quota_configured(asset).status == "fail"


class TestCheckPublicAccessQueryDisabled:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccessForQuery": "Disabled"})
        assert check_public_access_query_disabled(asset).status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccessForQuery": "Enabled"})
        assert check_public_access_query_disabled(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_public_access_query_disabled(asset).status == "fail"


class TestCheckPublicAccessIngestionDisabled:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccessForIngestion": "Disabled"})
        assert check_public_access_ingestion_disabled(asset).status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccessForIngestion": "Enabled"})
        assert check_public_access_ingestion_disabled(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_public_access_ingestion_disabled(asset).status == "fail"


class TestCheckResourcePermissionsOnly:
    def test_pass_when_enabled(self):
        asset = _make_asset(
            raw_properties={"features": {"enableLogAccessUsingOnlyResourcePermissions": True}}
        )
        assert check_resource_permissions_only(asset).status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(
            raw_properties={"features": {"enableLogAccessUsingOnlyResourcePermissions": False}}
        )
        assert check_resource_permissions_only(asset).status == "fail"

    def test_fail_when_features_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_resource_permissions_only(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_resource_permissions_only(asset).status == "fail"
