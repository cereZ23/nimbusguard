"""Unit tests for Container Registry checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.container_registry import (
    check_admin_disabled,
    check_public_access,
)


def _make_asset(
    resource_type: str = "microsoft.containerregistry/registries",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testacr",
        resource_type=resource_type,
        name="test-acr",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckAdminDisabled:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"adminUserEnabled": False})
        result = check_admin_disabled(asset)
        assert result.status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"adminUserEnabled": True})
        result = check_admin_disabled(asset)
        assert result.status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_admin_disabled(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_admin_disabled(asset)
        assert result.status == "pass"


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
