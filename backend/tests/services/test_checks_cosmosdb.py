"""Unit tests for Cosmos DB checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.cosmosdb import (
    check_public_access,
    check_vnet_filter,
)


def _make_asset(
    resource_type: str = "microsoft.documentdb/databaseaccounts",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testcosmos",
        resource_type=resource_type,
        name="test-cosmos",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckPublicAccess:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Disabled"})
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Enabled"})
        result = check_public_access(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_public_access(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_public_access(asset)
        assert result.status == "fail"


class TestCheckVnetFilter:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"isVirtualNetworkFilterEnabled": True})
        result = check_vnet_filter(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"isVirtualNetworkFilterEnabled": False})
        result = check_vnet_filter(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_vnet_filter(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_vnet_filter(asset)
        assert result.status == "fail"
