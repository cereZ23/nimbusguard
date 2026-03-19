from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api.router import api_router
from app.api.scim import router as scim_router
from app.config.settings import settings
from app.database import async_session
from app.exceptions import ConflictError, DomainError, NotFoundError
from app.logging_config import setup_logging
from app.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.rate_limit import limiter
from app.services.seed_controls import seed_controls

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with async_session() as db:
        count = await seed_controls(db)
        logger.info("Startup: seeded %d controls", count)
    yield
    # Shutdown: close Redis connection pool
    try:
        from app.services.cache import _redis, get_redis

        if _redis is not None:
            r = await get_redis()
            await r.aclose()
            logger.info("Redis connection closed")
    except Exception:
        pass


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.exception_handler(NotFoundError)
async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"data": None, "error": str(exc), "meta": None},
    )


@app.exception_handler(ConflictError)
async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"data": None, "error": str(exc), "meta": None},
    )


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"data": None, "error": str(exc), "meta": None},
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check — verifies DB and Redis connectivity."""
    checks: dict = {}
    healthy = True

    # Database check
    try:
        async with async_session() as db:
            await db.execute(select(1))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = "error"
        logger.warning("Health check: DB failed — %s", exc)
        healthy = False

    # Redis check
    try:
        from app.services.cache import get_redis

        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = "error"
        logger.warning("Health check: Redis failed — %s", exc)
        healthy = False

    status_code = 200 if healthy else 503
    from starlette.responses import JSONResponse as _JSONResponse

    return _JSONResponse(
        content={"status": "healthy" if healthy else "degraded", "checks": checks},
        status_code=status_code,
    )


from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, include_in_schema=False)

app.include_router(api_router, prefix="/api/v1")
app.include_router(scim_router, prefix="/scim/v2", tags=["scim"])
