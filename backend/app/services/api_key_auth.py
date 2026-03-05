"""API key authentication service — validates API keys for programmatic access."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.api_key import ApiKey
from app.models.user import User

logger = logging.getLogger(__name__)


async def authenticate_api_key(db: AsyncSession, api_key: str) -> User | None:
    """Look up an API key by its hash, verify validity, update last_used_at.

    Returns the associated User if valid, None otherwise.
    """
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = await db.execute(select(ApiKey).options(selectinload(ApiKey.user)).where(ApiKey.key_hash == key_hash))
    record = result.scalar_one_or_none()

    if record is None:
        logger.debug("API key not found")
        return None

    if not record.is_active:
        logger.warning("Inactive API key used: prefix=%s", record.key_prefix)
        return None

    if record.expires_at is not None:
        expires = record.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            logger.warning("Expired API key used: prefix=%s", record.key_prefix)
            return None

    # Update last_used_at
    record.last_used_at = datetime.now(UTC)
    await db.commit()

    user = record.user
    if user is None or not user.is_active:
        logger.warning("API key owner inactive: prefix=%s", record.key_prefix)
        return None

    logger.info("API key authenticated: prefix=%s user=%s", record.key_prefix, user.id)
    return user
