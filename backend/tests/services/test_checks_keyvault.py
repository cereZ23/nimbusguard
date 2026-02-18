"""Unit tests for Key Vault checks."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.keyvault import (
    check_key_expiration,
    check_network_acl,
    check_purge_protection,
    check_rbac_authorization,
    check_soft_delete,
)


def _make_asset(
    resource_type: str = "microsoft.keyvault/vaults",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testvault",
        resource_type=resource_type,
        name="test-vault",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckPurgeProtection:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"enablePurgeProtection": True})
        result = check_purge_protection(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"enablePurgeProtection": False})
        result = check_purge_protection(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_purge_protection(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_purge_protection(asset)
        assert result.status == "fail"


class TestCheckSoftDelete:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"enableSoftDelete": True})
        result = check_soft_delete(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"enableSoftDelete": False})
        result = check_soft_delete(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_soft_delete(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_soft_delete(asset)
        assert result.status == "fail"


class TestCheckKeyExpiration:
    def test_pass_when_expiration_set(self):
        asset = _make_asset(
            resource_type="microsoft.keyvault/vaults/keys",
            raw_properties={"attributes": {"expires": "2025-12-31T00:00:00Z"}},
        )
        result = check_key_expiration(asset)
        assert result.status == "pass"

    def test_fail_when_no_expiration(self):
        asset = _make_asset(
            resource_type="microsoft.keyvault/vaults/keys",
            raw_properties={"attributes": {}},
        )
        result = check_key_expiration(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(resource_type="microsoft.keyvault/vaults/keys", raw_properties={})
        result = check_key_expiration(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(resource_type="microsoft.keyvault/vaults/keys", raw_properties=None)
        result = check_key_expiration(asset)
        assert result.status == "fail"


class TestCheckNetworkAcl:
    def test_pass_when_deny(self):
        asset = _make_asset(raw_properties={"networkAcls": {"defaultAction": "Deny"}})
        result = check_network_acl(asset)
        assert result.status == "pass"

    def test_fail_when_allow(self):
        asset = _make_asset(raw_properties={"networkAcls": {"defaultAction": "Allow"}})
        result = check_network_acl(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_network_acl(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_network_acl(asset)
        assert result.status == "fail"


class TestCheckRbacAuthorization:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"enableRbacAuthorization": True})
        result = check_rbac_authorization(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"enableRbacAuthorization": False})
        result = check_rbac_authorization(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_rbac_authorization(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_rbac_authorization(asset)
        assert result.status == "fail"
