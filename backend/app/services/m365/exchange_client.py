"""Exchange Online admin client (app-only, read cmdlets).

Exchange Online / Defender-for-Office configuration (transport rules,
anti-phish, Safe Links, DKIM, audit config, ...) is not exposed through
Microsoft Graph. This client calls the Exchange admin REST endpoint that the
official ExchangeOnlineManagement PowerShell module uses under the hood:

    POST https://outlook.office365.com/adminapi/beta/{tenant}/InvokeCommand
    body: {"CmdletInput": {"CmdletName": "Get-...", "Parameters": {...}}}

The endpoint is semi-documented but stable and is the standard approach for
app-only M365 scanners (Prowler, Monkey365, ScubaGear all rely on it).

Requirements on the customer's Entra app registration:
- "Office 365 Exchange Online" application permission ``Exchange.ManageAsApp``
- a directory role on the service principal — Global Reader (recommended)
  or Exchange Administrator

Only ``Get-*`` cmdlets are allowed; anything else is rejected client-side.
"""

from __future__ import annotations

import logging
from typing import Any

from azure.identity import ClientSecretCredential

from app.utils.url_validation import create_ssrf_safe_client

logger = logging.getLogger(__name__)

EXO_BASE = "https://outlook.office365.com/adminapi/beta"
EXO_SCOPE = "https://outlook.office365.com/.default"


class ExchangeAdminError(Exception):
    """Raised when the Exchange admin API is unreachable or unauthorized."""

    def __init__(self, reason: str, status_code: int = 0) -> None:
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


class ExchangeAdminClient:
    """App-only client for read-only Exchange Online cmdlets."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self.tenant_id = tenant_id
        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._headers: dict[str, str] | None = None

    def authenticate(self) -> bool:
        """Acquire an Exchange admin token. Returns False when the app lacks
        the Exchange.ManageAsApp role or credentials are invalid."""
        try:
            token = self._credential.get_token(EXO_SCOPE)
        except Exception:
            logger.warning("M365: failed to get Exchange admin token for tenant %s", self.tenant_id)
            return False
        self._headers = {"Authorization": f"Bearer {token.token}"}
        return True

    async def run_cmdlet(self, name: str, parameters: dict[str, Any] | None = None) -> list[dict]:
        """Run a read-only cmdlet and return its result rows.

        Raises ExchangeAdminError on auth/permission/transport failures so the
        collector can record a structured collection marker.
        """
        if not name.startswith("Get-"):
            msg = f"Only Get-* cmdlets are allowed, got: {name}"
            raise ExchangeAdminError(msg)
        if self._headers is None:
            raise ExchangeAdminError("exchange_token_failed")

        payload = {"CmdletInput": {"CmdletName": name, "Parameters": parameters or {}}}
        url = f"{EXO_BASE}/{self.tenant_id}/InvokeCommand"
        try:
            async with create_ssrf_safe_client(timeout=60) as client:
                resp = await client.post(url, headers=self._headers, json=payload)
        except ExchangeAdminError:
            raise
        except Exception as exc:
            logger.exception("M365 Exchange: %s request failed", name)
            raise ExchangeAdminError("exchange_request_failed") from exc

        if resp.status_code in (401, 403):
            logger.warning(
                "M365 Exchange: %s returned %d — Exchange.ManageAsApp role or Global Reader assignment missing?",
                name,
                resp.status_code,
            )
            raise ExchangeAdminError("exchange_forbidden", status_code=resp.status_code)
        if resp.status_code != 200:
            logger.warning("M365 Exchange: %s returned %d", name, resp.status_code)
            raise ExchangeAdminError("exchange_error", status_code=resp.status_code)

        try:
            body = resp.json()
        except ValueError as exc:
            raise ExchangeAdminError("exchange_invalid_response") from exc
        return body.get("value", [])
