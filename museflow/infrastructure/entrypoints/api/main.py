from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter
from fastapi import Depends
from fastapi import FastAPI

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from museflow import __version__
from museflow.infrastructure.config.loggers import configure_loggers
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.api.dependencies import get_db
from museflow.infrastructure.entrypoints.api.schemas import HealthCheckResponse
from museflow.infrastructure.entrypoints.api.v1.endpoints.spotify import router as spotify_router
from museflow.infrastructure.entrypoints.api.v1.endpoints.users import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Only load configuration loggers at bootstrap, not at import (testing conflicts).
    configure_loggers(level=app_settings.LOG_LEVEL_API, handlers=app_settings.LOG_HANDLERS_API)
    yield


app = FastAPI(
    title="Museflow API",
    version=__version__,
    lifespan=lifespan,
    debug=app_settings.DEBUG,
)

api_v1_router = APIRouter()
api_v1_router.include_router(spotify_router, prefix="/spotify", tags=["spotify"])
api_v1_router.include_router(user_router, prefix="/users", tags=["users"])

app.include_router(api_v1_router, prefix=app_settings.API_V1_PREFIX)


@app.get("/health", name="health_check", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthCheckResponse:
    """Health check endpoint to verify application and database status."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        return HealthCheckResponse(status="unhealthy", database=f"error: {str(e)}")
    else:
        return HealthCheckResponse(status="healthy", database="connected")
