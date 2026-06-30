from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

# Import all model modules FIRST so SQLAlchemy can resolve relationship strings
# before any router (which imports models) triggers mapper configuration.
import app.auth.models  # noqa: F401
import app.organizations.models  # noqa: F401
import app.employees.models  # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401

from app.auth.router import router as auth_router
from app.core.config import settings
from app.health.router import router as health_router


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate cleaner operation IDs for Orval client generation."""
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — initialize and teardown resources here."""
    yield


app = FastAPI(
    title="OpenHuman API",
    version="0.1.0",
    description="OpenHuman — API backend",
    lifespan=lifespan,
    separate_input_output_schemas=False,
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
