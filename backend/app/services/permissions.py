from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)

# All granular permissions available in the system
ALL_PERMISSIONS = [
    "findings:read",
    "findings:write",
    "assets:read",
    "reports:read",
    "reports:generate",
    "accounts:read",
    "accounts:write",
    "users:read",
    "users:write",
    "scans:read",
    "scans:trigger",
    "integrations:read",
    "integrations:write",
    "settings:read",
    "settings:write",
]

# Human-readable descriptions for each permission
PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "findings:read": "View security findings",
    "findings:write": "Update finding status and assignments",
    "assets:read": "View cloud assets inventory",
    "reports:read": "View and download reports",
    "reports:generate": "Generate new reports and exports",
    "accounts:read": "View cloud account configurations",
    "accounts:write": "Add, edit, or remove cloud accounts",
    "users:read": "View team members",
    "users:write": "Invite, update, or remove users",
    "scans:read": "View scan history and status",
    "scans:trigger": "Trigger new security scans",
    "integrations:read": "View integration configurations",
    "integrations:write": "Configure webhooks, Slack, Jira, and other integrations",
    "settings:read": "View tenant settings",
    "settings:write": "Modify tenant settings",
}

# Permission categories for frontend grouping
PERMISSION_CATEGORIES: dict[str, list[str]] = {
    "Findings": ["findings:read", "findings:write"],
    "Assets": ["assets:read"],
    "Reports": ["reports:read", "reports:generate"],
    "Cloud Accounts": ["accounts:read", "accounts:write"],
    "Users": ["users:read", "users:write"],
    "Scans": ["scans:read", "scans:trigger"],
    "Integrations": ["integrations:read", "integrations:write"],
    "Settings": ["settings:read", "settings:write"],
}

# Built-in system roles that are created per tenant
SYSTEM_ROLES: dict[str, dict] = {
    "admin": {
        "name": "Administrator",
        "description": "Full access to all features and settings",
        "permissions": ["*"],
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to findings, assets, reports, and dashboards",
        "permissions": [
            "findings:read",
            "assets:read",
            "reports:read",
            "accounts:read",
            "scans:read",
            "integrations:read",
            "settings:read",
            "users:read",
        ],
    },
}


def get_user_permissions(user: User) -> list[str]:
    """Return the effective list of permissions for a user.

    Resolution order:
    1. If user has a custom_role loaded with permissions, use those.
    2. Fall back to the legacy ``user.role`` field and map via SYSTEM_ROLES.
    """
    # Custom role takes precedence when loaded
    if user.custom_role is not None:
        perms = user.custom_role.permissions
        if isinstance(perms, list):
            return perms
        return []

    # Fall back to legacy role field
    legacy = SYSTEM_ROLES.get(user.role)
    if legacy is not None:
        return legacy["permissions"]

    # Unknown role — no permissions
    logger.warning("Unknown legacy role '%s' for user %s", user.role, user.id)
    return []


def has_permission(user: User, permission: str) -> bool:
    """Check whether *user* holds a specific *permission*.

    The wildcard ``"*"`` grants all permissions (used by the admin system role).
    """
    perms = get_user_permissions(user)
    if "*" in perms:
        return True
    return permission in perms
