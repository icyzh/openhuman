"""
Shared test fixtures for CLI and Streamlit agent test tools.

Creates an isolated SQLite database with all tables and seeds a minimal
organisation + employee hierarchy so the agent graph has real data to work with.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure the api package is importable when running from the test/ directory
_this_dir = Path(__file__).resolve().parent
_api_dir = _this_dir.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

# Import models so their __table__ objects are registered
import app.auth.models  # noqa: F401  — User
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.employees.models  # noqa: F401  — Employee
import app.organizations.models  # noqa: F401  — Organization
from app.auth.models import User
from app.core.database import Base
from app.employees.models import Employee
from app.employees.templates import TEMPLATES, EmployeeTemplate
from app.organizations.models import Organization

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


# ---------------------------------------------------------------------------
# Pre-built seed employee configs — one per template
# ---------------------------------------------------------------------------

SEED_EMPLOYEES: list[dict] = [
    {
        "name": "Alex (HR)",
        "specialization": "hr_specialist",
        "role": "Human Resources Specialist",
        "personality": {"tone": "empathetic", "traits": ["professional", "supportive"]},
        "duties": ["Answer policy questions", "Screen resumes"],
    },
    {
        "name": "Blake (Sales)",
        "specialization": "sales_rep",
        "role": "Sales Development Representative",
        "personality": {"tone": "energetic", "traits": ["concise", "results-driven"]},
        "duties": ["Qualify leads", "Draft pipeline summaries"],
    },
    {
        "name": "Casey (Support)",
        "specialization": "support_agent",
        "role": "Customer Support Specialist",
        "personality": {"tone": "warm", "traits": ["patient", "empathetic"]},
        "duties": ["Answer support questions", "Escalate complex issues"],
    },
    {
        "name": "Drew (General)",
        "specialization": "general",
        "role": "AI Assistant",
        "personality": {"tone": "helpful", "traits": ["accurate", "concise"]},
        "duties": ["Answer general questions", "Help with research"],
    },
]

# Cached seed IDs so callers can reference them after setup
SEED_USER_ID: UUID | None = None
SEED_ORG_ID: UUID | None = None
SEED_EMPLOYEE_IDS: dict[str, UUID] = {}  # specialization → UUID


# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------


def _build_engine(db_path: str | Path) -> AsyncEngine:
    """Create an async SQLite engine with a UUID polyfill."""
    database_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(database_url)

    @event.listens_for(engine.sync_engine, "connect")
    def _register_uuid(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function("gen_random_uuid", 0, lambda: uuid4().hex)

    return engine


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_tables(engine: AsyncEngine) -> None:
    """Create all ORM tables inside an async SQLite database.

    Swaps PostgreSQL ``JSONB`` columns for ``JSON`` before DDL emission
    because SQLite has no JSONB type.
    """
    # Patch JSONB → JSON on every column in every table.  The ``type``
    # setter creates a copy of the Column so this is safe to do repeatedly
    # across different engines (e.g. when resetting).
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_data(session: AsyncSession) -> dict[str, UUID]:
    """Insert a test user, org, and four employees (one per template).

    Returns a dict mapping specialisation slug → employee UUID so callers
    can pick which employee to test.
    """
    global SEED_USER_ID, SEED_ORG_ID, SEED_EMPLOYEE_IDS  # noqa: PLW0603

    user_id = uuid4()
    org_id = uuid4()

    user = User(
        id=user_id,
        email="test@openhuman.local",
        password_hash="test-hash-not-real",
        name="Test User",
        is_active=True,
    )
    org = Organization(id=org_id, owner_id=user_id, name="Test Corp")

    session.add(user)
    session.add(org)

    employee_ids: dict[str, UUID] = {}
    for cfg in SEED_EMPLOYEES:
        emp_id = uuid4()
        template = TEMPLATES[cfg["specialization"]]
        emp = Employee(
            id=emp_id,
            org_id=org_id,
            name=cfg["name"],
            role=cfg["role"],
            specialization=cfg["specialization"],
            personality=cfg["personality"],
            duties=cfg["duties"],
            status="active",
        )
        session.add(emp)
        employee_ids[cfg["specialization"]] = emp_id

    await session.commit()

    SEED_USER_ID = user_id
    SEED_ORG_ID = org_id
    SEED_EMPLOYEE_IDS = employee_ids

    return employee_ids


async def setup_test_db(db_path: str | Path = ":memory:") -> tuple[AsyncEngine, async_sessionmaker, dict[str, UUID]]:
    """One-shot: create engine, tables, seed data.

    Returns (engine, session_factory, employee_ids).
    """
    engine = _build_engine(str(db_path))
    await create_tables(engine)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        employee_ids = await seed_data(session)

    return engine, session_factory, employee_ids


def print_banner() -> None:
    """Print a summary of available seed employees to the terminal."""
    print("\n📋 Available test employees:\n")
    for cfg in SEED_EMPLOYEES:
        template = TEMPLATES[cfg["specialization"]]
        eid = SEED_EMPLOYEE_IDS.get(cfg["specialization"], UUID(int=0))
        print(f"  {cfg['name']:<20s}  id={eid}")
        print(f"    Template : {template.name}")
        print(f"    Tools   : {', '.join(template.allowed_tools)}")
        print()
