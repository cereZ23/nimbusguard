"""Request middleware for logging context."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_var, tenant_id_var, user_id_var


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injects request_id and propagates tenant/user context for logging."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(rid)

        # tenant_id and user_id are set later by get_current_user
        tenant_id_var.set("")
        user_id_var.set("")

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
