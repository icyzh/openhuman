from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.auth.models  # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.employees.models  # noqa: F401
import app.organizations.models  # noqa: F401
import app.gateway.models  # noqa: F401
import app.agent.tools.mcp.models  # noqa: F401
from app.auth.models import User
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.database import get_db


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}"
    engine = create_async_engine(database_url)

    @event.listens_for(engine.sync_engine, "connect")
    def register_uuid_function(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function("gen_random_uuid", 0, lambda: uuid4().hex)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(User.__table__.create)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    test_app = FastAPI()
    test_app.include_router(auth_router)
    test_app.dependency_overrides[get_db] = override_get_db

    anyio.run(prepare_database)
    with TestClient(test_app) as test_client:
        yield test_client

    anyio.run(engine.dispose)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_clerk_auth(test_app: FastAPI, clerk_user_id: str, email: str, name: str):
    """Patch ``authenticate_request`` to return a signed-in Clerk user."""
    mock_request_state = MagicMock()
    mock_request_state.is_signed_in = True
    mock_request_state.message = None
    mock_request_state.payload = {
        "sub": clerk_user_id,
        "email": email,
        "name": name,
    }

    patcher = patch(
        "app.core.dependencies.authenticate_request",
        return_value=mock_request_state,
    )
    patcher.start()

    # Also set a valid secret key so authenticate_request doesn't fail early
    settings.clerk_secret_key = "sk_test_mock"

    return patcher


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_me_rejects_missing_token(client: TestClient) -> None:
    """Without a Bearer token the /me endpoint returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_user_when_authenticated(client: TestClient) -> None:
    """With a valid Clerk token, /me returns the user profile (auto-creating
    the local User row on first call)."""
    clerk_id = "user_mock_123"
    email = "ada@example.com"
    name = "Ada Lovelace"

    patcher = _mock_clerk_auth(client.app, clerk_id, email, name)

    try:
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer mock-session-token"},
        )
    finally:
        patcher.stop()

    assert response.status_code == 200
    user_payload = response.json()
    assert user_payload["email"] == email
    assert user_payload["name"] == name
    assert user_payload["clerk_id"] == clerk_id
    assert user_payload["is_active"] is True
    assert "password_hash" not in user_payload


def test_me_idempotent_across_calls(client: TestClient) -> None:
    """Calling /me twice with the same Clerk user returns the same local User."""
    clerk_id = "user_mock_456"
    email = "grace@example.com"
    name = "Grace Hopper"

    patcher = _mock_clerk_auth(client.app, clerk_id, email, name)

    try:
        first = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer t1"},
        )
        second = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer t2"},
        )
    finally:
        patcher.stop()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["email"] == email
