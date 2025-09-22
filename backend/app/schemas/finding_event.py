from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FindingEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    old_value: str | None = None
    new_value: str | None = None
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    details: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
