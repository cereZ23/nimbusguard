"""Rate limiter instance — imported by endpoints and wired in main.py."""

from __future__ import annotations

from slowapi import Limiter
from starlette.requests import Request

from app.config.settings import settings


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For behind reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 — take the first (client) IP
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # Fallback to direct connection IP
    if request.client:
        return request.client.host
    return "127.0.0.1"


limiter = Limiter(key_func=_get_client_ip, storage_uri=settings.redis_url)
