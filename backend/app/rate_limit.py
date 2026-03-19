"""Rate limiter instance — imported by endpoints and wired in main.py."""

from __future__ import annotations

import ipaddress

from slowapi import Limiter
from starlette.requests import Request

from app.config.settings import settings

# Known reverse proxy IPs — only trust X-Forwarded-For from these
_TRUSTED_PROXIES = {"127.0.0.1", "::1", "172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16"}


def _is_trusted_proxy(ip: str) -> bool:
    """Check if an IP belongs to a trusted proxy network."""
    try:
        addr = ipaddress.ip_address(ip)
        for cidr in _TRUSTED_PROXIES:
            if "/" in cidr:
                if addr in ipaddress.ip_network(cidr, strict=False):
                    return True
            elif ip == cidr:
                return True
    except ValueError:
        pass
    return False


def _get_client_ip(request: Request) -> str:
    """Extract real client IP. Only trust forwarded headers from known proxies."""
    direct_ip = request.client.host if request.client else "127.0.0.1"

    # Only parse X-Forwarded-For if the direct connection is from a trusted proxy
    if _is_trusted_proxy(direct_ip):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    return direct_ip


limiter = Limiter(key_func=_get_client_ip, storage_uri=settings.redis_url)
