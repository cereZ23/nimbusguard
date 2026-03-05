"""Unit tests for Log Analytics checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.log_analytics import check_cmk_encryption, check_retention_days


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
