from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WidgetLayout(BaseModel):
    widget: str = Field(min_length=1, max_length=50)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)
    config: dict[str, Any] = Field(default_factory=dict)


class CustomDashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    layout: list[WidgetLayout] = Field(default_factory=list)
    is_default: bool = False
    is_shared: bool = False


class CustomDashboardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    layout: list[WidgetLayout] | None = None
    is_default: bool | None = None
    is_shared: bool | None = None


class CustomDashboardResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    layout: list[WidgetLayout]
    is_default: bool
    is_shared: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WidgetData(BaseModel):
    widget: str
    data: Any


class DashboardDataResponse(BaseModel):
    dashboard_id: uuid.UUID
    widgets: list[WidgetData]
