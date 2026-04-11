from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    page: int
    size: int


class CursorMeta(BaseModel):
    """Meta block for cursor-paginated endpoints.

    Used on finding sub-collections (/timeline, /comments, /evidence)
    where page/size drifts when rows are inserted at the top between
    requests. The cursor is the `created_at` ISO timestamp of the last
    item in the returned page; pass it back as `?before=<cursor>` to
    fetch the next (older) page.
    """

    total: int
    limit: int
    has_more: bool
    next_cursor: str | None = None


class ApiResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: str | None = None
    meta: PaginationMeta | CursorMeta | None = None


class PaginationParams(BaseModel):
    page: int = 1
    size: int = 20
