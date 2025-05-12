from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExceptionCreateRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    expires_at: datetime | None = None


class ExceptionResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    reason: str
    status: str
    approved_by: str | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
