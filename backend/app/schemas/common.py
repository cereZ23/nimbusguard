from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    page: int
    size: int


class ApiResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: str | None = None
    meta: PaginationMeta | None = None


class PaginationParams(BaseModel):
    page: int = 1
    size: int = 20
