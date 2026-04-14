from __future__ import annotations

from pydantic import BaseModel, Field


class BrandingUpdate(BaseModel):
    primary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    company_name: str | None = Field(None, max_length=100)


class BrandingResponse(BaseModel):
    logo_url: str | None = None
    primary_color: str = "#6366f1"
    company_name: str = "CSPM"
    favicon_url: str | None = None
