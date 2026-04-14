"""Unit tests for storage account checks (CIS-AZ-95..99)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.storage import (
    check_cross_tenant_delegation_sas_disabled,
    check_cross_tenant_replication_disabled,
    check_default_oauth_auth,
    check_public_network_access_disabled,
    check_standard_dns_endpoint,
)


def _make_asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.Storage/storageAccounts/teststor",
        resource_type="microsoft.storage/storageaccounts",
        name="teststor",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCrossTenantReplication:
    def test_pass_when_false(self):
        asset = _make_asset({"allowCrossTenantReplication": False})
        assert check_cross_tenant_replication_disabled(asset).status == "pass"

    def test_fail_when_true(self):
        asset = _make_asset({"allowCrossTenantReplication": True})
        assert check_cross_tenant_replication_disabled(asset).status == "fail"

    def test_fail_when_missing(self):
        # Missing defaults to True (Azure legacy default) → fail.
        asset = _make_asset({})
        assert check_cross_tenant_replication_disabled(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        assert check_cross_tenant_replication_disabled(asset).status == "fail"


class TestDefaultOAuthAuth:
    def test_pass_when_true(self):
        asset = _make_asset({"defaultToOAuthAuthentication": True})
        assert check_default_oauth_auth(asset).status == "pass"

    def test_fail_when_false(self):
        asset = _make_asset({"defaultToOAuthAuthentication": False})
        assert check_default_oauth_auth(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset({})
        assert check_default_oauth_auth(asset).status == "fail"


class TestCrossTenantDelegationSas:
    def test_pass_when_false(self):
        asset = _make_asset({"allowCrossTenantDelegationSas": False})
        assert check_cross_tenant_delegation_sas_disabled(asset).status == "pass"

    def test_fail_when_true(self):
        asset = _make_asset({"allowCrossTenantDelegationSas": True})
        assert check_cross_tenant_delegation_sas_disabled(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset({})
        assert check_cross_tenant_delegation_sas_disabled(asset).status == "fail"


class TestPublicNetworkAccessDisabled:
    def test_pass_when_no_private_endpoint(self):
        asset = _make_asset({"publicNetworkAccess": "Enabled", "privateEndpointConnections": []})
        assert check_public_network_access_disabled(asset).status == "pass"

    def test_pass_when_private_endpoint_and_disabled(self):
        asset = _make_asset(
            {
                "publicNetworkAccess": "Disabled",
                "privateEndpointConnections": [{"id": "pe1"}],
            }
        )
        assert check_public_network_access_disabled(asset).status == "pass"

    def test_fail_when_private_endpoint_and_public_enabled(self):
        asset = _make_asset(
            {
                "publicNetworkAccess": "Enabled",
                "privateEndpointConnections": [{"id": "pe1"}],
            }
        )
        assert check_public_network_access_disabled(asset).status == "fail"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(None)
        assert check_public_network_access_disabled(asset).status == "pass"


class TestStandardDnsEndpoint:
    def test_pass_when_standard(self):
        asset = _make_asset({"dnsEndpointType": "Standard"})
        assert check_standard_dns_endpoint(asset).status == "pass"

    def test_pass_when_standard_lowercase(self):
        asset = _make_asset({"dnsEndpointType": "standard"})
        assert check_standard_dns_endpoint(asset).status == "pass"

    def test_fail_when_azure_dns_zone(self):
        asset = _make_asset({"dnsEndpointType": "AzureDnsZone"})
        assert check_standard_dns_endpoint(asset).status == "fail"

    def test_pass_when_missing(self):
        # Missing defaults to Standard (Azure default behavior).
        asset = _make_asset({})
        assert check_standard_dns_endpoint(asset).status == "pass"
