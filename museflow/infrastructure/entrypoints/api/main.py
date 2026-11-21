import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter
from fastapi import Depends
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from museflow import __version__
from museflow.infrastructure.config.loggers.setup import configure_loggers
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.api.dependencies import get_session_factory
from museflow.infrastructure.entrypoints.api.errors import add_exception_handlers
from museflow.infrastructure.entrypoints.api.schemas import HealthCheckResponse
from museflow.infrastructure.entrypoints.api.v1.endpoints.playlists import router as playlist_router
from museflow.infrastructure.entrypoints.api.v1.endpoints.provider import router as provider_router
from museflow.infrastructure.entrypoints.api.v1.endpoints.users import router as user_router
from museflow.infrastructure.entrypoints.wiring import Wiring

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Only load configuration loggers at bootstrap, not at import (testing conflicts).
    configure_loggers(
        level=app_settings.LOG_LEVEL_API,
        third_party_level=app_settings.LOG_LEVEL_THIRD_PARTY,
        handlers=app_settings.LOG_HANDLERS_API,
    )

    # Opened in the server's event loop, in the process that serves (never before a fork).
    async with Wiring.open() as wiring:
        app.state.wiring = wiring
        yield


app = FastAPI(
    title="Museflow API",
    version=__version__,
    lifespan=lifespan,
    debug=app_settings.DEBUG,
)
add_exception_handlers(app)

# CORS middleware must be added at the top of the list to prevent any side effect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in app_settings.BACKEND_CORS_ALLOW_ORIGINS],
    allow_methods=app_settings.BACKEND_CORS_ALLOW_METHODS,
    allow_headers=app_settings.BACKEND_CORS_ALLOW_HEADERS,
    allow_credentials=app_settings.BACKEND_CORS_ALLOW_CREDENTIALS,
    expose_headers=app_settings.BACKEND_CORS_EXPOSE_HEADERS,
    max_age=app_settings.BACKEND_CORS_MAX_AGE,
)

api_v1_router = APIRouter()
# Static prefixes first: "/{provider}" would otherwise shadow any of their "/connect" routes.
api_v1_router.include_router(user_router, prefix="/users", tags=["users"])
api_v1_router.include_router(playlist_router, prefix="/playlists", tags=["playlists"])
api_v1_router.include_router(provider_router, prefix="/{provider}", tags=["provider"])

app.include_router(api_v1_router, prefix=app_settings.API_V1_PREFIX)


@app.get("/health", name="health_check", tags=["health"])
async def health_check(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> HealthCheckResponse:
    """Health check endpoint to verify application and database status."""
    # A raw session, the health check's only: everything else goes through the unit of work.
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health Check Failed")
        return HealthCheckResponse(status="unhealthy", database="unavailable")
    else:
        return HealthCheckResponse(status="healthy", database="connected")
