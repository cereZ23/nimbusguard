"""Finding timeline service — records events for finding history tracking."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding_event import FindingEvent

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    *,
    finding_id: uuid.UUID,
    event_type: str,
    old_value: str | None = None,
    new_value: str | None = None,
    user_id: uuid.UUID | None = None,
    details: str | None = None,
) -> FindingEvent:
    """Insert a finding timeline event.

    Does NOT commit — callers are responsible for transaction management.
    """
    event = FindingEvent(
        finding_id=finding_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        user_id=user_id,
        details=details,
    )
    db.add(event)
    await db.flush()
    logger.info(
        "Finding event: type=%s finding=%s user=%s old=%s new=%s",
        event_type,
        finding_id,
        user_id,
        old_value,
        new_value,
    )
    return event
