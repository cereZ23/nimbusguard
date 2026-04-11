"""Unit tests for diagnostic settings sweep checks (CIS-AZ-154..163)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.asset import Asset
from app.services.azure.checks.diagnostic_settings import (
    check_aks_diagnostic_settings,
    check_app_gateway_diagnostic_settings,
    check_cosmos_diagnostic_settings,
    check_frontdoor_diagnostic_settings,
    check_keyvault_diagnostic_settings,
    check_nsg_diagnostic_settings,
    check_servicebus_diagnostic_settings,
    check_sql_database_diagnostic_settings,
    check_vm_diagnostic_settings,
    check_webapp_diagnostic_settings,
)


def _asset(resource_type: str, raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/r",
        resource_type=resource_type,
        name="r",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _with_workspace(workspace_id: str = "/subscriptions/.../workspaces/w") -> dict:
    return {
        "diagnosticSettings": [
            {
                "id": "/subscriptions/.../diagnosticSettings/default",
                "name": "default",
                "workspaceId": workspace_id,
                "storageAccountId": None,
                "eventHubName": None,
                "logs_count": 5,
                "metrics_count": 3,
            }
        ]
    }


def _with_storage(storage_id: str = "/subscriptions/.../storageAccounts/s") -> dict:
    return {
        "diagnosticSettings": [
            {
                "id": "/subscriptions/.../diagnosticSettings/archive",
                "name": "archive",
                "workspaceId": None,
                "storageAccountId": storage_id,
                "eventHubName": None,
                "logs_count": 2,
                "metrics_count": 0,
            }
        ]
    }


def _with_setting_no_destination() -> dict:
    return {
        "diagnosticSettings": [
            {
                "id": "/subscriptions/.../diagnosticSettings/broken",
                "name": "broken",
                "workspaceId": None,
                "storageAccountId": None,
                "eventHubName": None,
                "logs_count": 0,
                "metrics_count": 0,
            }
        ]
    }


# Parametrised over the 10 checks so the core logic is validated once per
# resource type while keeping the test file concise.
_CASES = [
    ("microsoft.sql/servers/databases", check_sql_database_diagnostic_settings),
    ("microsoft.keyvault/vaults", check_keyvault_diagnostic_settings),
    ("microsoft.web/sites", check_webapp_diagnostic_settings),
    ("microsoft.compute/virtualmachines", check_vm_diagnostic_settings),
    ("microsoft.documentdb/databaseaccounts", check_cosmos_diagnostic_settings),
    ("microsoft.containerservice/managedclusters", check_aks_diagnostic_settings),
    ("microsoft.network/applicationgateways", check_app_gateway_diagnostic_settings),
    ("microsoft.network/frontdoors", check_frontdoor_diagnostic_settings),
    ("microsoft.servicebus/namespaces", check_servicebus_diagnostic_settings),
    ("microsoft.network/networksecuritygroups", check_nsg_diagnostic_settings),
]


@pytest.mark.parametrize(("rt", "fn"), _CASES)
def test_pass_with_workspace_destination(rt, fn):
    asset = _asset(rt, _with_workspace())
    assert fn(asset).status == "pass"


@pytest.mark.parametrize(("rt", "fn"), _CASES)
def test_pass_with_storage_destination(rt, fn):
    asset = _asset(rt, _with_storage())
    assert fn(asset).status == "pass"


@pytest.mark.parametrize(("rt", "fn"), _CASES)
def test_fail_no_diagnostic_settings(rt, fn):
    asset = _asset(rt, {})
    assert fn(asset).status == "fail"


@pytest.mark.parametrize(("rt", "fn"), _CASES)
def test_fail_empty_list(rt, fn):
    asset = _asset(rt, {"diagnosticSettings": []})
    assert fn(asset).status == "fail"


@pytest.mark.parametrize(("rt", "fn"), _CASES)
def test_fail_setting_without_destination(rt, fn):
    asset = _asset(rt, _with_setting_no_destination())
    assert fn(asset).status == "fail"


@pytest.mark.parametrize(("rt", "fn"), _CASES)
def test_fail_raw_properties_none(rt, fn):
    asset = _asset(rt, None)
    assert fn(asset).status == "fail"


def test_pass_when_multiple_settings_some_valid():
    """At least one setting with a destination is enough."""
    asset = _asset(
        "microsoft.keyvault/vaults",
        {
            "diagnosticSettings": [
                {
                    "id": "bad",
                    "name": "bad",
                    "workspaceId": None,
                    "storageAccountId": None,
                    "eventHubName": None,
                    "logs_count": 0,
                    "metrics_count": 0,
                },
                {
                    "id": "good",
                    "name": "good",
                    "workspaceId": "/subscriptions/.../workspaces/w",
                    "storageAccountId": None,
                    "eventHubName": None,
                    "logs_count": 3,
                    "metrics_count": 2,
                },
            ]
        },
    )
    assert check_keyvault_diagnostic_settings(asset).status == "pass"


def test_pass_with_eventhub_destination():
    asset = _asset(
        "microsoft.sql/servers/databases",
        {
            "diagnosticSettings": [
                {
                    "id": "eh",
                    "name": "eh",
                    "workspaceId": None,
                    "storageAccountId": None,
                    "eventHubName": "siem-forwarder",
                    "logs_count": 4,
                    "metrics_count": 1,
                }
            ]
        },
    )
    assert check_sql_database_diagnostic_settings(asset).status == "pass"
