"""Diagnostic settings sweep (CIS-AZ-154..163).

Verifies that each critical Azure resource type has diagnostic settings
configured (forwarding logs and metrics to Log Analytics, a storage
account, or an Event Hub).

The data is collected by ``collector.py::_collect_diagnostic_settings()``
which queries ``microsoft.insights/diagnosticsettings`` via Resource Graph
and patches each target asset's ``raw_properties['diagnosticSettings']``
with a list of summaries. Each entry has the shape::

    {
        "id": "<full diagnostic setting id>",
        "name": "<setting name>",
        "workspaceId": "<LA workspace id>" | None,
        "storageAccountId": "<storage id>" | None,
        "eventHubName": "<eh name>" | None,
        "logs_count": int,
        "metrics_count": int,
    }

Evaluators pass when the list is present and non-empty AND at least one
setting has a destination (workspaceId, storageAccountId or eventHubName).
If the collector did not populate the field (e.g. Resource Graph does not
index diagnostic settings for that service yet), the check reports fail
as a secure default.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


def _setting_has_destination(setting: dict) -> bool:
    """Return True if a diagnostic setting summary has at least one sink."""
    if not isinstance(setting, dict):
        return False
    return bool(setting.get("workspaceId") or setting.get("storageAccountId") or setting.get("eventHubName"))


def _evaluate_diagnostic_settings(asset: Asset, *, service_label: str) -> EvalResult:
    """Shared implementation — pass if the asset has at least one valid setting."""
    props = asset.raw_properties or {}
    settings = props.get("diagnosticSettings")
    if not isinstance(settings, list) or not settings:
        return EvalResult(
            status="fail",
            evidence={"diagnosticSettings_count": 0},
            description=(
                f"{service_label} has no diagnostic settings configured — "
                "logs and metrics are not being exported to Log Analytics, "
                "Storage or Event Hub, breaking audit trail and alerting"
            ),
        )

    valid = [s for s in settings if _setting_has_destination(s)]
    if not valid:
        return EvalResult(
            status="fail",
            evidence={"diagnosticSettings_count": len(settings), "with_destination": 0},
            description=(
                f"{service_label} has {len(settings)} diagnostic setting(s) but none "
                "points to a log sink — attach Log Analytics workspace, storage account "
                "or Event Hub to the setting"
            ),
        )

    return EvalResult(
        status="pass",
        evidence={
            "diagnosticSettings_count": len(settings),
            "with_destination": len(valid),
        },
        description=(
            f"{service_label} has {len(valid)} diagnostic setting(s) routing logs and metrics to at least one sink"
        ),
    )


# ── CIS-AZ-154..163: one check per resource type ───────────────────


@check("microsoft.sql/servers/databases", "CIS-AZ-154")
def check_sql_database_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-154: SQL database should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="SQL database")


@check("microsoft.keyvault/vaults", "CIS-AZ-155")
def check_keyvault_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-155: Key Vault should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Key Vault")


@check("microsoft.web/sites", "CIS-AZ-156")
def check_webapp_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-156: Web App should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Web App")


@check("microsoft.compute/virtualmachines", "CIS-AZ-157")
def check_vm_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-157: Virtual machine should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Virtual machine")


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-158")
def check_cosmos_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-158: Cosmos DB account should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Cosmos DB account")


@check("microsoft.containerservice/managedclusters", "CIS-AZ-159")
def check_aks_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-159: AKS cluster should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="AKS cluster")


@check("microsoft.network/applicationgateways", "CIS-AZ-160")
def check_app_gateway_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-160: Application Gateway should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Application Gateway")


@check("microsoft.network/frontdoors", "CIS-AZ-161")
def check_frontdoor_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-161: Front Door should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Front Door")


@check("microsoft.servicebus/namespaces", "CIS-AZ-162")
def check_servicebus_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-162: Service Bus namespace should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="Service Bus namespace")


@check("microsoft.network/networksecuritygroups", "CIS-AZ-163")
def check_nsg_diagnostic_settings(asset: Asset) -> EvalResult:
    """CIS-AZ-163: NSG should have diagnostic settings configured."""
    return _evaluate_diagnostic_settings(asset, service_label="NSG")
