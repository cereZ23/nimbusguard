"""Unit tests for AKS checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.aks import (
    check_network_policy,
    check_rbac_enabled,
)


def _make_asset(
    resource_type: str = "microsoft.containerservice/managedclusters",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testaks",
        resource_type=resource_type,
        name="test-aks",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckRbacEnabled:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"enableRBAC": True})
        result = check_rbac_enabled(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"enableRBAC": False})
        result = check_rbac_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_rbac_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_rbac_enabled(asset)
        assert result.status == "fail"


class TestCheckNetworkPolicy:
    def test_pass_when_calico(self):
        asset = _make_asset(raw_properties={"networkProfile": {"networkPolicy": "calico"}})
        result = check_network_policy(asset)
        assert result.status == "pass"

    def test_pass_when_azure(self):
        asset = _make_asset(raw_properties={"networkProfile": {"networkPolicy": "azure"}})
        result = check_network_policy(asset)
        assert result.status == "pass"

    def test_fail_when_none_value(self):
        asset = _make_asset(raw_properties={"networkProfile": {"networkPolicy": "none"}})
        result = check_network_policy(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_network_policy(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_network_policy(asset)
        assert result.status == "fail"
