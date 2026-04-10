"""Azure CIS-lite check modules.

Importing this package registers all check functions in the global CheckRegistry.
"""

from __future__ import annotations

from app.services.azure.checks import (  # noqa: F401
    activity_alerts,
    aks,
    app_gateway,
    backup,
    batch,
    compute,
    container_registry,
    cosmosdb,
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
    webapp,
)
