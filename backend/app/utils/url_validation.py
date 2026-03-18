"""Shared URL validation utilities — SSRF protection for all outbound URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def validate_public_url(url: str, *, require_https: bool = True) -> str:
    """Validate that a URL points to a public, non-internal address.

    Blocks private IPs, loopback, link-local, and reserved ranges.
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
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                msg = f"URL must not resolve to a private or reserved IP address ({ip})"
                raise ValueError(msg)
    except socket.gaierror as exc:
        msg = f"Cannot resolve hostname: {hostname}"
        raise ValueError(msg) from exc

    return url
