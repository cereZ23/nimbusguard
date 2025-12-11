from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ControlMapping(BaseModel):
    control_code: str
    group: str = ""
    reference: str = ""


class CustomFrameworkCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    control_mappings: list[ControlMapping] = Field(..., min_length=1)


class CustomFrameworkUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    control_mappings: list[ControlMapping] | None = None
    is_active: bool | None = None


class CustomFrameworkResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    control_mappings: list[dict]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ControlComplianceItem(BaseModel):
    control_code: str
    control_name: str
    severity: str
    group: str
    reference: str
    pass_count: int
    fail_count: int
    total_count: int


class CustomFrameworkCompliance(BaseModel):
    framework_id: uuid.UUID
    framework_name: str
    controls: list[ControlComplianceItem]
    total_controls: int
    passing_controls: int
    failing_controls: int
