"""Microsoft Graph client for M365 posture collection (app-only).

Thin async wrapper around httpx using the same SSRF-safe client factory and
ClientSecretCredential token flow as the Azure Entra collector. All methods
degrade gracefully: HTTP errors are returned as status codes, never raised,
so a missing permission on one endpoint never fails the whole scan.
"""

from __future__ import annotations

import logging
from typing import Any

from azure.identity import ClientSecretCredential

from app.utils.url_validation import create_ssrf_safe_client

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# Safety valve for @odata.nextLink paging — 50 pages x 999 items is far
# beyond any tenant-level policy collection this client is used for.
_MAX_PAGES = 50


class M365GraphClient:
    """App-only Microsoft Graph client (client-credentials flow)."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self.tenant_id = tenant_id
        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._headers: dict[str, str] | None = None

    def authenticate(self) -> bool:
        """Acquire a Graph token. Returns False when credentials are invalid."""
        try:
            token = self._credential.get_token(GRAPH_SCOPE)
        except Exception:
            logger.warning("M365: failed to get Graph token for tenant %s", self.tenant_id)
            return False
        self._headers = {"Authorization": f"Bearer {token.token}"}
        return True

    def _require_headers(self) -> dict[str, str]:
        if self._headers is None:
            msg = "M365GraphClient used before authenticate()"
            raise RuntimeError(msg)
        return self._headers

    async def get_json(self, path: str, extra_headers: dict[str, str] | None = None) -> tuple[int, dict | None]:
        """GET a Graph path (e.g. "/organization"). Returns (status_code, body|None)."""
        headers = dict(self._require_headers())
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with create_ssrf_safe_client(timeout=30) as client:
                resp = await client.get(f"{GRAPH_BASE}{path}", headers=headers)
        except Exception:
            logger.exception("M365 Graph: request failed for %s", path)
            return 0, None
        if resp.status_code != 200:
            logger.warning("M365 Graph: %s returned %d", path, resp.status_code)
            return resp.status_code, None
        try:
            return 200, resp.json()
        except ValueError:
            logger.warning("M365 Graph: %s returned non-JSON body", path)
            return 200, None

    async def get_all(self, path: str, extra_headers: dict[str, str] | None = None) -> tuple[int, list[Any]]:
        """GET a collection path, following @odata.nextLink. Returns (status, items).

        The status is the first response's status code; paging stops silently
        on any non-200 continuation page (partial data beats a failed scan).
        """
        headers = dict(self._require_headers())
        if extra_headers:
            headers.update(extra_headers)
        items: list[Any] = []
        url = f"{GRAPH_BASE}{path}"
        first_status = 0
        try:
            async with create_ssrf_safe_client(timeout=30) as client:
                for page in range(_MAX_PAGES):
                    resp = await client.get(url, headers=headers)
                    if page == 0:
                        first_status = resp.status_code
                    if resp.status_code != 200:
                        if page == 0:
                            logger.warning("M365 Graph: %s returned %d", path, resp.status_code)
                        break
                    body = resp.json()
                    items.extend(body.get("value", []))
                    next_link = body.get("@odata.nextLink")
                    if not next_link:
                        break
                    url = next_link
        except Exception:
            logger.exception("M365 Graph: paged request failed for %s", path)
        return first_status, items
