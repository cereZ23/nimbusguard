"""Rate limiter instance — imported by endpoints and wired in main.py."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
