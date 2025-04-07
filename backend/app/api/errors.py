from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class ClientError(BaseModel):
    message: str = Field(max_length=2000)
    stack: str | None = Field(None, max_length=5000)
    component: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=500)
    user_agent: str | None = Field(None, max_length=500)


@router.post("/client-errors", status_code=204)
async def report_client_error(body: ClientError, request: Request) -> None:
    logger.error(
        "Client error: %s",
        body.message,
        extra={
            "error_stack": body.stack,
            "error_component": body.component,
            "error_url": body.url,
            "client_ip": request.client.host if request.client else None,
            "user_agent": body.user_agent or request.headers.get("user-agent"),
        },
    )
