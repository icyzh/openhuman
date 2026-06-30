from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterRequest
from app.core.security import create_access_token, hash_password, verify_password


async def register(db: AsyncSession, data: RegisterRequest) -> User:
    """Create a new user. Raises ValueError if email is taken."""
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise ValueError("A user with this email already exists")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """Return the User if credentials are valid, otherwise None."""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by their UUID string."""
    return await db.scalar(select(User).where(User.id == user_id))


def make_token_response(user: User) -> dict:
    """Build a TokenResponse dict from a User."""
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
    }
