from __future__ import annotations

import uuid

from pydantic import BaseModel


class ControlResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    severity: str
    framework: str
    remediation_hint: str | None
    framework_mappings: dict | None = None
    pass_count: int = 0
    fail_count: int = 0
    total_count: int = 0

    model_config = {"from_attributes": True}


class ControlSummary(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    severity: str
    framework: str
    framework_mappings: dict | None = None

    model_config = {"from_attributes": True}
