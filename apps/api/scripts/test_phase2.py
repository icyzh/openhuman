import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory

# All models must be imported
import app.auth.models  # noqa
import app.organizations.models  # noqa
import app.employees.models  # noqa
import app.channel_assignments.models  # noqa
import app.documents.models  # noqa

from app.auth.models import User
from app.auth.schemas import RegisterRequest
from app.auth.service import register as register_user, authenticate
from app.core.security import create_access_token, decode_access_token


async def test():
    # Clean up from previous test
    async with async_session_factory() as db:
        existing = await db.scalar(select(User).where(User.email == "p2@test.com"))
        if existing:
            await db.delete(existing)
            await db.commit()

    # 1. Register
    async with async_session_factory() as db:
        data = RegisterRequest(email="p2@test.com", password="secret", name="Phase2")
        saved = await register_user(db, data)
        print(f"Register OK: id={saved.id} email={saved.email} name={saved.name}")
        assert saved.password_hash != "secret", "password not hashed!"
        assert saved.password_hash.startswith("$2"), f"unexpected hash: {saved.password_hash[:20]}"
        print(f"  password hashed: {saved.password_hash[:30]}...")

    # 2. Login correct
    async with async_session_factory() as db:
        authed = await authenticate(db, "p2@test.com", "secret")
        assert authed is not None
        print("Login OK: correct password accepted")

    # 3. Login wrong
    async with async_session_factory() as db:
        bad = await authenticate(db, "p2@test.com", "wrong")
        assert bad is None
        print("Login OK: wrong password rejected")

    # 4. Duplicate register
    async with async_session_factory() as db:
        data = RegisterRequest(email="p2@test.com", password="x", name="Dup")
        try:
            await register_user(db, data)
            assert False, "should have raised ValueError"
        except ValueError as e:
            print(f"Register OK: duplicate rejected — {e}")

    # 5. JWT
    token = create_access_token(str(saved.id))
    payload = decode_access_token(token)
    assert payload["sub"] == str(saved.id)
    print(f"JWT OK: sub={payload['sub'][:8]}... exp={payload['exp']}")

    # 6. User lookup (simulates get_current_user internals)
    async with async_session_factory() as db:
        fetched = await db.scalar(select(User).where(User.id == saved.id))
        assert fetched is not None
        print(f"User lookup OK: {fetched.email}")

    # 7. TokenResponse format
    from app.auth.service import make_token_response
    resp = make_token_response(saved)
    assert "access_token" in resp
    assert resp["token_type"] == "bearer"
    print(f"TokenResponse OK: token_type={resp['token_type']}")

    print()
    print("Phase 2: all checks passed")


asyncio.run(test())
