"""Unit tests for ACR supply-chain checks (CIS-AZ-135..140)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.acr_supply_chain import (
    check_acr_cmk_encryption,
    check_anonymous_pull_disabled,
    check_content_trust_enabled,
    check_network_rule_default_deny,
    check_quarantine_policy_enabled,
    check_retention_policy_enabled,
)


def _acr(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.ContainerRegistry/registries/r",
        resource_type="microsoft.containerregistry/registries",
        name="acr",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestAnonymousPullDisabled:
    def test_pass_disabled(self):
        assert check_anonymous_pull_disabled(_acr({"anonymousPullEnabled": False})).status == "pass"

    def test_pass_missing_defaults_false(self):
        assert check_anonymous_pull_disabled(_acr({})).status == "pass"

    def test_fail_enabled(self):
        assert check_anonymous_pull_disabled(_acr({"anonymousPullEnabled": True})).status == "fail"

    def test_pass_raw_properties_none(self):
        assert check_anonymous_pull_disabled(_acr(None)).status == "pass"


class TestNetworkRuleDefaultDeny:
    def test_pass_deny(self):
        assert check_network_rule_default_deny(_acr({"networkRuleSet": {"defaultAction": "Deny"}})).status == "pass"

    def test_pass_public_access_disabled_regardless_of_rule_set(self):
        asset = _acr({"publicNetworkAccess": "Disabled", "networkRuleSet": {"defaultAction": "Allow"}})
        assert check_network_rule_default_deny(asset).status == "pass"

    def test_fail_allow(self):
        assert check_network_rule_default_deny(_acr({"networkRuleSet": {"defaultAction": "Allow"}})).status == "fail"

    def test_fail_missing(self):
        assert check_network_rule_default_deny(_acr({})).status == "fail"


class TestQuarantinePolicyEnabled:
    def test_pass(self):
        asset = _acr({"policies": {"quarantinePolicy": {"status": "enabled"}}})
        assert check_quarantine_policy_enabled(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _acr({"policies": {"quarantinePolicy": {"status": "disabled"}}})
        assert check_quarantine_policy_enabled(asset).status == "fail"

    def test_fail_missing(self):
        assert check_quarantine_policy_enabled(_acr({})).status == "fail"


class TestContentTrustEnabled:
    def test_pass(self):
        asset = _acr({"policies": {"trustPolicy": {"status": "enabled", "type": "Notary"}}})
        assert check_content_trust_enabled(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _acr({"policies": {"trustPolicy": {"status": "disabled"}}})
        assert check_content_trust_enabled(asset).status == "fail"

    def test_fail_missing(self):
        assert check_content_trust_enabled(_acr({})).status == "fail"


class TestRetentionPolicyEnabled:
    def test_pass(self):
        asset = _acr({"policies": {"retentionPolicy": {"status": "enabled", "days": 30}}})
        assert check_retention_policy_enabled(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _acr({"policies": {"retentionPolicy": {"status": "disabled"}}})
        assert check_retention_policy_enabled(asset).status == "fail"

    def test_fail_missing(self):
        assert check_retention_policy_enabled(_acr({})).status == "fail"


class TestAcrCmkEncryption:
    def test_pass(self):
        asset = _acr(
            {
                "encryption": {
                    "status": "enabled",
                    "keyVaultProperties": {"keyIdentifier": "https://kv.vault.azure.net/keys/k/1"},
                }
            }
        )
        assert check_acr_cmk_encryption(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _acr({"encryption": {"status": "disabled"}})
        assert check_acr_cmk_encryption(asset).status == "fail"

    def test_fail_missing_key_identifier(self):
        asset = _acr({"encryption": {"status": "enabled", "keyVaultProperties": {}}})
        assert check_acr_cmk_encryption(asset).status == "fail"

    def test_fail_missing(self):
        assert check_acr_cmk_encryption(_acr({})).status == "fail"
