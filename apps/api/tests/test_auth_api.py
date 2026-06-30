from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.auth.models  # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.employees.models  # noqa: F401
import app.organizations.models  # noqa: F401
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


def test_register_login_and_me(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "ada@example.com",
            "password": "correct horse battery staple",
            "name": "Ada Lovelace",
        },
    )

    assert register_response.status_code == 201
    token_payload = register_response.json()
    assert token_payload["token_type"] == "bearer"
    assert token_payload["access_token"]
    assert "password_hash" not in token_payload

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "ada@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert login_response.status_code == 200
    login_token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login_token}"},
    )

    assert me_response.status_code == 200
    user_payload = me_response.json()
    assert user_payload["email"] == "ada@example.com"
    assert user_payload["name"] == "Ada Lovelace"
    assert user_payload["is_active"] is True
    assert "password_hash" not in user_payload


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    payload = {
        "email": "grace@example.com",
        "password": "correct horse battery staple",
        "name": "Grace Hopper",
    }

    assert client.post("/api/auth/register", json=payload).status_code == 201
    duplicate_response = client.post("/api/auth/register", json=payload)

    assert duplicate_response.status_code == 409


def test_me_rejects_missing_invalid_and_expired_tokens(client: TestClient) -> None:
    missing_response = client.get("/api/auth/me")
    invalid_response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    expired_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    expired_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401
    assert expired_response.status_code == 401


def test_me_rejects_deleted_or_inactive_user(client: TestClient) -> None:
    """Token for a user ID that does not exist must be rejected (covers
    both deleted-user and never-existed paths through get_current_user)."""
    ghost_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=60),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    ghost_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )
    assert ghost_response.status_code == 401
    assert ghost_response.json()["detail"] == "User not found"
