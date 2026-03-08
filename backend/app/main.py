from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

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


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
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
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
app.include_router(scim_router, prefix="/scim/v2", tags=["scim"])
