"""Unit tests for azure.subscription_collector.

The collector wraps the Azure SDK; tests use monkeypatch to replace the SDK
client constructors with in-memory fakes so we can exercise the aggregation
and graceful-degradation logic without hitting Azure.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.azure import subscription_collector


class _FakePricingResult:
    def __init__(self, value):
        self.value = value


class _FakeSecurityCenter:
    """Minimal fake of azure.mgmt.security.SecurityCenter."""

    # Class-level knobs so tests can tweak behaviour per-instance via monkeypatch.
    pricings_value = None
    contacts_value = None
    auto_provisioning_value = None
    raise_on_pricings = False
    raise_on_contacts = False
    raise_on_auto_provisioning = False

    def __init__(self, credential, subscription_id):
        self.pricings = SimpleNamespace(list=self._list_pricings)
        self.security_contacts = SimpleNamespace(list=self._list_contacts)
        self.auto_provisioning_settings = SimpleNamespace(get=self._get_auto_provisioning)

    def _list_pricings(self):
        if type(self).raise_on_pricings:
            raise RuntimeError("pricings API failed")
        return _FakePricingResult(type(self).pricings_value or [])

    def _list_contacts(self):
        if type(self).raise_on_contacts:
            raise RuntimeError("contacts API failed")
        return type(self).contacts_value or []

    def _get_auto_provisioning(self, name):
        if type(self).raise_on_auto_provisioning:
            raise RuntimeError("auto-provisioning API failed")
        return type(self).auto_provisioning_value


class _FakeAuthorizationClient:
    """Minimal fake of azure.mgmt.authorization.AuthorizationManagementClient."""

    role_assignments_value = None
    raise_on_list = False

    def __init__(self, credential, subscription_id):
        self.role_assignments = SimpleNamespace(list_for_subscription=self._list)

    def _list(self):
        if type(self).raise_on_list:
            raise RuntimeError("role_assignments API failed")
        return type(self).role_assignments_value or []


@pytest.fixture(autouse=True)
def _reset_fakes():
    """Reset class-level knobs on every test so state does not leak."""
    _FakeSecurityCenter.pricings_value = None
    _FakeSecurityCenter.contacts_value = None
    _FakeSecurityCenter.auto_provisioning_value = None
    _FakeSecurityCenter.raise_on_pricings = False
    _FakeSecurityCenter.raise_on_contacts = False
    _FakeSecurityCenter.raise_on_auto_provisioning = False
    _FakeAuthorizationClient.role_assignments_value = None
    _FakeAuthorizationClient.raise_on_list = False


@pytest.fixture
def patch_sdk(monkeypatch):
    """Replace the Azure SDK client constructors with the fakes above."""
    import azure.mgmt.authorization as auth_mod
    import azure.mgmt.security as sec_mod

    monkeypatch.setattr(sec_mod, "SecurityCenter", _FakeSecurityCenter)
    monkeypatch.setattr(auth_mod, "AuthorizationManagementClient", _FakeAuthorizationClient)
    return monkeypatch


# ── Happy path ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_happy_path(patch_sdk):
    _FakeSecurityCenter.pricings_value = [
        SimpleNamespace(name="VirtualMachines", pricing_tier="Standard"),
        SimpleNamespace(name="StorageAccounts", pricing_tier="Free"),
        SimpleNamespace(name="KeyVaults", pricing_tier="Standard"),
    ]
    _FakeSecurityCenter.contacts_value = [
        SimpleNamespace(email="soc@example.com", alert_notifications="On"),
    ]
    _FakeSecurityCenter.auto_provisioning_value = SimpleNamespace(auto_provision="On")
    owner_role_id = (
        "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    )
    contributor_role_id = (
        "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c"
    )
    _FakeAuthorizationClient.role_assignments_value = [
        SimpleNamespace(role_definition_id=owner_role_id),
        SimpleNamespace(role_definition_id=owner_role_id),
        SimpleNamespace(role_definition_id=contributor_role_id),
    ]

    state = await subscription_collector.collect_subscription_state(credential=None, subscription_id="sub-id")

    assert state["subscription_id"] == "sub-id"
    assert state["defender_plans"] == {
        "VirtualMachines": "Standard",
        "StorageAccounts": "Free",
        "KeyVaults": "Standard",
    }
    assert len(state["security_contacts"]) == 1
    assert state["security_contacts"][0]["email"] == "soc@example.com"
    assert state["security_contacts"][0]["alert_notifications"] is True
    assert state["auto_provisioning"] == "On"
    assert state["owner_count"] == 2  # two Owner assignments, Contributor ignored
    assert state["_errors"] == []


# ── Graceful degradation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_pricings_failure_is_recorded(patch_sdk):
    _FakeSecurityCenter.raise_on_pricings = True
    _FakeSecurityCenter.contacts_value = []
    _FakeSecurityCenter.auto_provisioning_value = SimpleNamespace(auto_provision="Off")
    _FakeAuthorizationClient.role_assignments_value = []

    state = await subscription_collector.collect_subscription_state(credential=None, subscription_id="sub-id")

    assert state["defender_plans"] is None
    assert any(e["source"] == "defender_plans" for e in state["_errors"])
    # Other sources still succeed.
    assert state["auto_provisioning"] == "Off"
    assert state["owner_count"] == 0


@pytest.mark.asyncio
async def test_collect_all_failures(patch_sdk):
    _FakeSecurityCenter.raise_on_pricings = True
    _FakeSecurityCenter.raise_on_contacts = True
    _FakeSecurityCenter.raise_on_auto_provisioning = True
    _FakeAuthorizationClient.raise_on_list = True

    state = await subscription_collector.collect_subscription_state(credential=None, subscription_id="sub-id")

    assert state["defender_plans"] is None
    assert state["security_contacts"] is None
    assert state["auto_provisioning"] is None
    assert state["owner_count"] is None
    sources = {e["source"] for e in state["_errors"]}
    assert sources == {"defender_plans", "security_contacts", "auto_provisioning", "owner_count"}


# ── Helper: alert_notifications object-style vs string-style ───────


@pytest.mark.asyncio
async def test_contact_alert_notifications_object_style(patch_sdk):
    _FakeSecurityCenter.contacts_value = [
        SimpleNamespace(
            email="soc@example.com",
            alert_notifications=SimpleNamespace(state="On", minimal_severity="Low"),
        )
    ]

    state = await subscription_collector.collect_subscription_state(credential=None, subscription_id="sub-id")
    assert state["security_contacts"][0]["alert_notifications"] is True


@pytest.mark.asyncio
async def test_contact_alert_notifications_missing(patch_sdk):
    _FakeSecurityCenter.contacts_value = [SimpleNamespace(email="soc@example.com", alert_notifications=None)]

    state = await subscription_collector.collect_subscription_state(credential=None, subscription_id="sub-id")
    assert state["security_contacts"][0]["alert_notifications"] is None


# ── is_defender_plan_enabled helper ────────────────────────────────


def test_is_defender_plan_enabled_standard():
    assert subscription_collector.is_defender_plan_enabled({"X": "Standard"}, "X") is True


def test_is_defender_plan_enabled_free():
    assert subscription_collector.is_defender_plan_enabled({"X": "Free"}, "X") is False


def test_is_defender_plan_enabled_missing_plan():
    assert subscription_collector.is_defender_plan_enabled({"Y": "Standard"}, "X") is False


def test_is_defender_plan_enabled_none():
    assert subscription_collector.is_defender_plan_enabled(None, "X") is False


def test_is_defender_plan_enabled_not_dict():
    assert subscription_collector.is_defender_plan_enabled("garbage", "X") is False  # type: ignore[arg-type]
