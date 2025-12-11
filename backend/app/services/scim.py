"""SCIM 2.0 service — maps between SCIM User resources and internal User model."""
from __future__ import annotations

import logging
import re
from typing import Any

from app.models.user import User

logger = logging.getLogger(__name__)


# ── Mapping helpers ───────────────────────────────────────────────────


def user_to_scim_resource(user: User, base_url: str = "") -> dict[str, Any]:
    """Convert an internal User model instance to a SCIM 2.0 User resource dict."""
    full_name = user.full_name or ""
    name_parts = full_name.split(maxsplit=1)
    given_name = name_parts[0] if name_parts else ""
    family_name = name_parts[1] if len(name_parts) > 1 else ""

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "externalId": user.scim_external_id,
        "userName": user.email,
        "name": {
            "formatted": full_name,
            "givenName": given_name,
            "familyName": family_name,
        },
        "displayName": full_name,
        "emails": [
            {
                "value": user.email,
                "type": "work",
                "primary": True,
            }
        ],
        "active": user.is_active,
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat() if user.created_at else None,
            "lastModified": user.updated_at.isoformat() if user.updated_at else None,
            "location": f"{base_url}/scim/v2/Users/{user.id}" if base_url else None,
        },
    }


def scim_resource_to_user_data(scim_data: dict[str, Any]) -> dict[str, Any]:
    """Extract internal user fields from a SCIM create/replace request body.

    Returns a dict with keys: email, full_name, is_active, scim_external_id.
    """
    result: dict[str, Any] = {}

    # Email — prefer primary email from emails array, fallback to userName
    email = scim_data.get("userName")
    emails = scim_data.get("emails")
    if emails and isinstance(emails, list):
        for entry in emails:
            if isinstance(entry, dict) and entry.get("primary"):
                email = entry.get("value", email)
                break
        if email is None and emails:
            email = emails[0].get("value")
    result["email"] = email

    # Full name — prefer name.formatted, then displayName, then construct from parts
    name = scim_data.get("name") or {}
    full_name = name.get("formatted") if isinstance(name, dict) else None
    if not full_name:
        full_name = scim_data.get("displayName")
    if not full_name and isinstance(name, dict):
        parts = [name.get("givenName", ""), name.get("familyName", "")]
        full_name = " ".join(p for p in parts if p).strip()
    if not full_name:
        # Fallback to local part of email
        full_name = (email or "").split("@")[0]
    result["full_name"] = full_name

    # Active flag
    if "active" in scim_data:
        result["is_active"] = bool(scim_data["active"])

    # External ID
    if "externalId" in scim_data:
        result["scim_external_id"] = scim_data["externalId"]

    return result


def apply_scim_patch(user: User, operations: list[dict[str, Any]]) -> None:
    """Apply SCIM Patch operations (RFC 7644 Section 3.5.2) to a User model in-place.

    Supported paths:
    - active (bool)
    - userName (maps to email)
    - name.givenName, name.familyName, name.formatted, displayName (maps to full_name)
    - externalId (maps to scim_external_id)
    - emails[type eq "work"].value (maps to email)
    """
    for op_data in operations:
        op = op_data.get("op", "").lower()
        path = op_data.get("path", "")
        value = op_data.get("value")

        if op not in ("add", "replace", "remove"):
            logger.warning("Unsupported SCIM patch op: %s", op)
            continue

        if op == "remove":
            # Only support removing externalId
            if path == "externalId":
                user.scim_external_id = None
            continue

        # op is "add" or "replace"
        if path == "active":
            user.is_active = bool(value)
        elif path == "userName":
            user.email = str(value)
        elif path in ("displayName", "name.formatted"):
            user.full_name = str(value)
        elif path == "name.givenName":
            # Replace first name, keep last name
            parts = (user.full_name or "").split(maxsplit=1)
            family = parts[1] if len(parts) > 1 else ""
            user.full_name = f"{value} {family}".strip()
        elif path == "name.familyName":
            # Replace last name, keep first name
            parts = (user.full_name or "").split(maxsplit=1)
            given = parts[0] if parts else ""
            user.full_name = f"{given} {value}".strip()
        elif path == "externalId":
            user.scim_external_id = str(value) if value is not None else None
        elif path and "emails" in path:
            # Handle emails[type eq "work"].value or similar
            if isinstance(value, str):
                user.email = value
            elif isinstance(value, list) and value:
                for entry in value:
                    if isinstance(entry, dict) and entry.get("primary", False):
                        user.email = entry["value"]
                        break
                else:
                    user.email = value[0].get("value", user.email)
        elif not path and isinstance(value, dict):
            # No path — value is a dict of attributes to set
            if "active" in value:
                user.is_active = bool(value["active"])
            if "userName" in value:
                user.email = str(value["userName"])
            if "displayName" in value:
                user.full_name = str(value["displayName"])
            if "externalId" in value:
                user.scim_external_id = str(value["externalId"]) if value["externalId"] is not None else None
            if "name" in value and isinstance(value["name"], dict):
                name = value["name"]
                formatted = name.get("formatted")
                if formatted:
                    user.full_name = formatted
                else:
                    parts = [name.get("givenName", ""), name.get("familyName", "")]
                    user.full_name = " ".join(p for p in parts if p).strip() or user.full_name


# ── SCIM Filter parsing ──────────────────────────────────────────────

# Matches: attrName op "value"  or  attrName op value
_FILTER_PATTERN = re.compile(
    r'^(\w+(?:\.\w+)?)\s+(eq|ne|co|sw|ew)\s+"?([^"]*)"?$',
    re.IGNORECASE,
)


def parse_scim_filter(filter_str: str | None) -> list[tuple[str, str, str]]:
    """Parse a simple SCIM filter string into a list of (attribute, operator, value) tuples.

    Supports:
    - userName eq "john@example.com"
    - externalId eq "abc123"
    - active eq true
    - active eq false
    - Compound filters with 'and' (e.g., userName eq "x" and active eq true)

    Returns an empty list if filter_str is None or cannot be parsed.
    """
    if not filter_str:
        return []

    results: list[tuple[str, str, str]] = []

    # Split by 'and' (case-insensitive)
    parts = re.split(r"\s+and\s+", filter_str, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        match = _FILTER_PATTERN.match(part)
        if match:
            attr, op, val = match.groups()
            results.append((attr, op.lower(), val))

    return results


async def apply_scim_filters(
    query: Any,
    filters: list[tuple[str, str, str]],
) -> Any:
    """Apply parsed SCIM filters to a SQLAlchemy select query.

    Returns the modified query.
    """
    for attr, op, val in filters:
        if attr == "userName" and op == "eq":
            query = query.where(User.email == val)
        elif attr == "externalId" and op == "eq":
            query = query.where(User.scim_external_id == val)
        elif attr == "active" and op == "eq":
            active = val.lower() in ("true", "1")
            query = query.where(User.is_active == active)
        elif attr == "displayName" and op == "eq":
            query = query.where(User.full_name == val)
        else:
            logger.debug("Unsupported SCIM filter: %s %s %s", attr, op, val)

    return query
