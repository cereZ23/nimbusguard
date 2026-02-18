"""Unit tests for PostgreSQL checks."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.postgresql import (
    check_log_checkpoints,
    check_ssl_enforcement,
)


def _make_asset(
    resource_type: str = "microsoft.dbforpostgresql/flexibleservers",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testpg",
        resource_type=resource_type,
        name="test-pg",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckSslEnforcement:
    def test_pass_when_ssl_enabled(self):
        asset = _make_asset(raw_properties={"sslEnforcement": "Enabled"})
        result = check_ssl_enforcement(asset)
        assert result.status == "pass"

    def test_pass_when_secure_transport_on(self):
        asset = _make_asset(raw_properties={"requireSecureTransport": "ON"})
        result = check_ssl_enforcement(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"sslEnforcement": "Disabled"})
        result = check_ssl_enforcement(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_ssl_enforcement(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_ssl_enforcement(asset)
        assert result.status == "fail"


class TestCheckLogCheckpoints:
    def test_pass_when_on(self):
        asset = _make_asset(raw_properties={"serverParameters": {"log_checkpoints": "ON"}})
        result = check_log_checkpoints(asset)
        assert result.status == "pass"

    def test_pass_when_flat_property(self):
        asset = _make_asset(raw_properties={"log_checkpoints": "ON"})
        result = check_log_checkpoints(asset)
        assert result.status == "pass"

    def test_fail_when_off(self):
        asset = _make_asset(raw_properties={"serverParameters": {"log_checkpoints": "OFF"}})
        result = check_log_checkpoints(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_log_checkpoints(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_log_checkpoints(asset)
        assert result.status == "fail"
