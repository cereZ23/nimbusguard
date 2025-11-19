from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SavedFilterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    page: str = Field(pattern=r"^(findings|assets)$")
    filters: dict
    description: str | None = None


class SavedFilterResponse(BaseModel):
    id: uuid.UUID
    name: str
    page: str
    filters: dict
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
