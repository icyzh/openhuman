from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
import subprocess
import sys

print(">>> [Startup] Running database migrations...", flush=True)
try:
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print(">>> [Startup] Database migrations completed successfully!", flush=True)
except Exception as e:
    print(f">>> [Startup] Database migrations failed: {e}", flush=True)
    sys.exit(1)

# ── Cognee bootstrap: MUST run before any import app.* that triggers import cognee ──
from app.core.cognee import apply_cognee_config
apply_cognee_config()
# ────────────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

# Import all model modules FIRST so SQLAlchemy can resolve relationship strings
# before any router (which imports models) triggers mapper configuration.
import app.auth.models  # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.employees.models  # noqa: F401
import app.organizations.models  # noqa: F401
import app.agent.tools.mcp.models  # noqa: F401
import app.gateway.models  # noqa: F401
from app.agent.checkpointer import close_checkpointer, init_checkpointer
from app.agent.router import router as agent_router
from app.auth.router import router as auth_router
from app.channel_assignments.router import router as ca_router
from app.core.config import settings
from app.documents.router import router as doc_router
from app.employees.router import router as emp_router
from app.gateway.manager import BotGatewayManager
from app.gateway.router import router as slack_slots_router
from app.gateway.slack_oauth import router as slack_oauth_router
from app.health.router import router as health_router
from app.mcp.router import oauth_router as mcp_oauth_router
from app.mcp.router import router as mcp_router
from app.memory.router import router as memory_router
from app.memory.service import init_cognee
from app.organizations.router import router as org_router

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate cleaner operation IDs for Orval client generation."""
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — initialize and teardown resources here."""
    print(">>> LIFESPAN STARTING...", flush=True)
    # ── Cognee startup ──────────────────────────────────────────────────
    try:
        print(">>> Initializing Cognee...", flush=True)
        await init_cognee()
        print(">>> Cognee initialized successfully!", flush=True)
    except Exception as e:
        print(f">>> Cognee initialization failed: {e}", flush=True)
        logger.exception(
            "Cognee initialization failed — continuing without memory"
        )
    # Phase 4: Postgres checkpointer for agent thread memory / pause-resume.
    print(">>> Initializing checkpointer...", flush=True)
    await init_checkpointer()
    print(">>> Checkpointer initialized successfully!", flush=True)

    print(">>> Starting bot gateway...", flush=True)
    gateway_manager = BotGatewayManager()
    if settings.gateway_enabled:
        await gateway_manager.start()
    print(">>> Lifespan startup completed successfully!", flush=True)
    try:
        yield
    finally:
        # -- Shutdown ----------------------------------------------------------
        print(">>> Lifespan shutting down...", flush=True)
        if settings.gateway_enabled:
            await gateway_manager.stop()
        await close_checkpointer()
        print(">>> Lifespan shutdown completed!", flush=True)


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
    allow_origin_regex=r"https://openhuman\.icyzh\.dev|https://openhooman\.icyzh\.dev|https://.*\.vercel\.app|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(org_router)
app.include_router(emp_router)
app.include_router(ca_router)
app.include_router(doc_router)
app.include_router(agent_router)
app.include_router(memory_router)
app.include_router(slack_oauth_router)
app.include_router(slack_slots_router)
app.include_router(mcp_router)
app.include_router(mcp_oauth_router)

