"""Microsoft 365 CIS check modules.

Importing this package registers all check functions in the global CheckRegistry.
"""

from __future__ import annotations

from app.services.m365.checks import (  # noqa: F401
    defender,
    exchange,
    identity,
    purview,
    sharepoint,
    teams,
)
