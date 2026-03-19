"""Shared URL validation utilities — SSRF protection for all outbound URLs."""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _check_ip_is_public(ip_str: str) -> None:
    """Raise ValueError if IP is private, loopback, link-local, or reserved."""
    ip = ipaddress.ip_address(ip_str)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        msg = f"URL must not resolve to a private or reserved IP address ({ip})"
        raise ValueError(msg)


def validate_public_url(url: str, *, require_https: bool = True) -> str:
    """Validate that a URL points to a public, non-internal address.

    Blocks private IPs, loopback, link-local, and reserved ranges.
    Used at schema validation time (input check).
    Raises ValueError on validation failure.
    """
    parsed = urlparse(url)

    if require_https and parsed.scheme != "https":
        msg = "URL must use https:// scheme"
        raise ValueError(msg)
    if not require_https and parsed.scheme not in ("https", "http"):
        msg = "URL must use https:// or http:// scheme"
        raise ValueError(msg)

    hostname = parsed.hostname
    if not hostname:
        msg = "URL must contain a valid hostname"
        raise ValueError(msg)

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        msg = "URL must not point to localhost or loopback addresses"
        raise ValueError(msg)

    # Resolve hostname and block private/link-local IP ranges
    try:
        addrs = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in addrs:
            _check_ip_is_public(sockaddr[0])
    except socket.gaierror as exc:
        msg = f"Cannot resolve hostname: {hostname}"
        raise ValueError(msg) from exc

    return url


def create_ssrf_safe_client(timeout: int = 10) -> httpx.AsyncClient:
    """Create an httpx client that validates resolved IPs at connection time.

    This prevents DNS rebinding / TOCTOU attacks by checking the IP
    at the moment the TCP connection is made, not at validation time.
    """

    class _SsrfSafeTransport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            # Re-resolve and validate IP at request time
            hostname = request.url.host
            if hostname:
                if hostname.lower() in _BLOCKED_HOSTNAMES:
                    msg = f"SSRF blocked: {hostname} is a blocked hostname"
                    raise httpx.ConnectError(msg)
                try:
                    addrs = socket.getaddrinfo(
                        hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
                    )
                    for _family, _type, _proto, _canonname, sockaddr in addrs:
                        _check_ip_is_public(sockaddr[0])
                except socket.gaierror as exc:
                    msg = f"SSRF blocked: cannot resolve {hostname}"
                    raise httpx.ConnectError(msg) from exc
                except ValueError as exc:
                    raise httpx.ConnectError(str(exc)) from exc

            return await super().handle_async_request(request)

    return httpx.AsyncClient(
        transport=_SsrfSafeTransport(),
        timeout=timeout,
        follow_redirects=False,
    )
