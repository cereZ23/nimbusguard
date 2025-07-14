"""Azure CIS-lite check modules.

Importing this package registers all check functions in the global CheckRegistry.
"""
from __future__ import annotations

from app.services.azure.checks import (  # noqa: F401
    activity_alerts,
    aks,
    app_gateway,
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
    nic,
    nsg,
    postgresql,
    rbac,
    redis,
    servicebus,
    sql,
    storage,
    webapp,
)
