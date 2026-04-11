"""Azure CIS-lite check modules.

Importing this package registers all check functions in the global CheckRegistry.
"""

from __future__ import annotations

from app.services.azure.checks import (  # noqa: F401
    acr_supply_chain,
    activity_alerts,
    aks,
    aks_hardening,
    app_gateway,
    backup,
    batch,
    compute,
    container_registry,
    cosmosdb,
    db_flex_hardening,
    diagnostic_settings,
    eventhub,
    front_door,
    keyvault,
    log_analytics,
    managed_disk,
    mysql,
    network,
    network_exposure,
    nic,
    nsg,
    postgresql,
    rbac,
    redis,
    serverfarms,
    servicebus,
    sql,
    storage,
    subscription,
    vm_hardening,
    webapp,
)
