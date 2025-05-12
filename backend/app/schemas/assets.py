from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AssetResponse(BaseModel):
    id: uuid.UUID
    provider_id: str
    resource_type: str
    name: str
    region: str | None
    tags: dict | None
    first_seen_at: datetime
    last_seen_at: datetime
    cloud_account_id: uuid.UUID

    model_config = {"from_attributes": True}
