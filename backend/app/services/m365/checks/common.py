"""Shared helpers for Microsoft 365 checks.

The M365 collector only stores a raw_properties key when the corresponding
endpoint/cmdlet succeeded, so a missing key means "not collected this scan"
and the check must return None (skip) rather than assert pass or fail.
"""

from __future__ import annotations

from typing import Any

from app.models.asset import Asset


def prop(asset: Asset, key: str) -> Any | None:
    """Return the collected value for ``key``, or None when it was not
    collected (permission gap / endpoint failure). Collected values are
    always dicts or lists, never None, so ``is None`` is unambiguous."""
    return (asset.raw_properties or {}).get(key)
