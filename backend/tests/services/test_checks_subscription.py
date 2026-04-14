"""Unit tests for subscription-level checks (CIS-AZ-104..113)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.subscription import (
    check_auto_provisioning_enabled,
    check_defender_for_app_service,
    check_defender_for_containers,
    check_defender_for_key_vault,
    check_defender_for_servers,
    check_defender_for_sql,
    check_defender_for_storage,
    check_security_contact_alert_notifications,
    check_security_contact_email,
    check_subscription_owner_count,
)


def _make_asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        resource_type="microsoft.subscription/subscription",
        name="Subscription test",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


# ── Defender for X plan checks ───────────────────────────────────────


class TestDefenderForServers:
    def test_pass_when_standard(self):
        asset = _make_asset({"defender_plans": {"VirtualMachines": "Standard"}})
        assert check_defender_for_servers(asset).status == "pass"

    def test_fail_when_free(self):
        asset = _make_asset({"defender_plans": {"VirtualMachines": "Free"}})
        assert check_defender_for_servers(asset).status == "fail"

    def test_fail_when_missing_plan(self):
        asset = _make_asset({"defender_plans": {}})
        assert check_defender_for_servers(asset).status == "fail"

    def test_fail_when_collection_error(self):
        asset = _make_asset(
            {
                "defender_plans": None,
                "_errors": [{"source": "defender_plans", "error": "403 Forbidden"}],
            }
        )
        result = check_defender_for_servers(asset)
        assert result.status == "fail"
        assert "collector_error" in result.evidence

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        assert check_defender_for_servers(asset).status == "fail"


class TestDefenderForStorage:
    def test_pass_when_standard(self):
        asset = _make_asset({"defender_plans": {"StorageAccounts": "Standard"}})
        assert check_defender_for_storage(asset).status == "pass"

    def test_fail_when_free(self):
        asset = _make_asset({"defender_plans": {"StorageAccounts": "Free"}})
        assert check_defender_for_storage(asset).status == "fail"


class TestDefenderForSql:
    def test_pass_when_standard(self):
        asset = _make_asset({"defender_plans": {"SqlServers": "Standard"}})
        assert check_defender_for_sql(asset).status == "pass"

    def test_fail_when_free(self):
        asset = _make_asset({"defender_plans": {"SqlServers": "Free"}})
        assert check_defender_for_sql(asset).status == "fail"


class TestDefenderForAppService:
    def test_pass_when_standard(self):
        asset = _make_asset({"defender_plans": {"AppServices": "Standard"}})
        assert check_defender_for_app_service(asset).status == "pass"

    def test_fail_when_free(self):
        asset = _make_asset({"defender_plans": {"AppServices": "Free"}})
        assert check_defender_for_app_service(asset).status == "fail"


class TestDefenderForContainers:
    def test_pass_when_standard(self):
        asset = _make_asset({"defender_plans": {"Containers": "Standard"}})
        assert check_defender_for_containers(asset).status == "pass"

    def test_fail_when_free(self):
        asset = _make_asset({"defender_plans": {"Containers": "Free"}})
        assert check_defender_for_containers(asset).status == "fail"


class TestDefenderForKeyVault:
    def test_pass_when_standard(self):
        asset = _make_asset({"defender_plans": {"KeyVaults": "Standard"}})
        assert check_defender_for_key_vault(asset).status == "pass"

    def test_fail_when_free(self):
        asset = _make_asset({"defender_plans": {"KeyVaults": "Free"}})
        assert check_defender_for_key_vault(asset).status == "fail"


# ── Security contacts ────────────────────────────────────────────────


class TestSecurityContactEmail:
    def test_pass_when_contact_with_email(self):
        asset = _make_asset({"security_contacts": [{"email": "soc@example.com", "alert_notifications": True}]})
        assert check_security_contact_email(asset).status == "pass"

    def test_fail_when_no_contacts(self):
        asset = _make_asset({"security_contacts": []})
        assert check_security_contact_email(asset).status == "fail"

    def test_fail_when_contacts_none(self):
        asset = _make_asset({"security_contacts": None})
        assert check_security_contact_email(asset).status == "fail"

    def test_fail_when_contact_without_email(self):
        asset = _make_asset({"security_contacts": [{"email": None, "alert_notifications": True}]})
        assert check_security_contact_email(asset).status == "fail"

    def test_fail_when_collection_error(self):
        asset = _make_asset(
            {
                "security_contacts": None,
                "_errors": [{"source": "security_contacts", "error": "timeout"}],
            }
        )
        result = check_security_contact_email(asset)
        assert result.status == "fail"
        assert result.evidence.get("collector_error") == "timeout"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        assert check_security_contact_email(asset).status == "fail"


class TestSecurityContactAlertNotifications:
    def test_pass_when_notifications_on(self):
        asset = _make_asset({"security_contacts": [{"email": "soc@example.com", "alert_notifications": True}]})
        assert check_security_contact_alert_notifications(asset).status == "pass"

    def test_fail_when_notifications_off(self):
        asset = _make_asset({"security_contacts": [{"email": "soc@example.com", "alert_notifications": False}]})
        assert check_security_contact_alert_notifications(asset).status == "fail"

    def test_fail_when_no_contacts(self):
        asset = _make_asset({"security_contacts": []})
        assert check_security_contact_alert_notifications(asset).status == "fail"

    def test_pass_when_any_contact_has_notifications(self):
        # At least one contact with notifications enabled is enough.
        asset = _make_asset(
            {
                "security_contacts": [
                    {"email": "dev@example.com", "alert_notifications": False},
                    {"email": "soc@example.com", "alert_notifications": True},
                ]
            }
        )
        assert check_security_contact_alert_notifications(asset).status == "pass"


# ── Auto-provisioning ────────────────────────────────────────────────


class TestAutoProvisioning:
    def test_pass_when_on(self):
        asset = _make_asset({"auto_provisioning": "On"})
        assert check_auto_provisioning_enabled(asset).status == "pass"

    def test_pass_when_lowercase_on(self):
        asset = _make_asset({"auto_provisioning": "on"})
        assert check_auto_provisioning_enabled(asset).status == "pass"

    def test_fail_when_off(self):
        asset = _make_asset({"auto_provisioning": "Off"})
        assert check_auto_provisioning_enabled(asset).status == "fail"

    def test_fail_when_none(self):
        asset = _make_asset({"auto_provisioning": None})
        assert check_auto_provisioning_enabled(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset({})
        assert check_auto_provisioning_enabled(asset).status == "fail"

    def test_fail_when_collection_error(self):
        asset = _make_asset(
            {
                "auto_provisioning": None,
                "_errors": [{"source": "auto_provisioning", "error": "perm denied"}],
            }
        )
        result = check_auto_provisioning_enabled(asset)
        assert result.status == "fail"
        assert "collector_error" in result.evidence


# ── Subscription owner count ─────────────────────────────────────────


class TestSubscriptionOwnerCount:
    def test_pass_when_one_owner(self):
        asset = _make_asset({"owner_count": 1})
        assert check_subscription_owner_count(asset).status == "pass"

    def test_pass_when_exactly_three(self):
        asset = _make_asset({"owner_count": 3})
        assert check_subscription_owner_count(asset).status == "pass"

    def test_fail_when_four(self):
        asset = _make_asset({"owner_count": 4})
        assert check_subscription_owner_count(asset).status == "fail"

    def test_fail_when_many(self):
        asset = _make_asset({"owner_count": 15})
        assert check_subscription_owner_count(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset({})
        assert check_subscription_owner_count(asset).status == "fail"

    def test_fail_when_collection_error(self):
        asset = _make_asset(
            {
                "owner_count": None,
                "_errors": [{"source": "owner_count", "error": "403 Forbidden"}],
            }
        )
        result = check_subscription_owner_count(asset)
        assert result.status == "fail"

    def test_pass_when_zero_owners(self):
        # Edge case: a brand-new subscription could theoretically have 0 owners.
        # The rule only flags *too many*, so 0 still passes the upper-bound check.
        asset = _make_asset({"owner_count": 0})
        assert check_subscription_owner_count(asset).status == "pass"
