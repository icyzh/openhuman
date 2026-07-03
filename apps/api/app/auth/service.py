from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


async def get_or_create_user(db: AsyncSession, clerk_id: str, clerk_payload: dict) -> User:
    """Look up a local User by Clerk ID, creating one on first login."""
    user = await db.scalar(select(User).where(User.clerk_id == clerk_id))
    if user is not None:
        return user

    # Extract info from Clerk's JWT payload
    email = clerk_payload.get("email") or clerk_payload.get("email_address")
    if not email:
        email = f"{clerk_id}@noemail.clerk.user"

    first_name = clerk_payload.get("first_name", "")
    last_name = clerk_payload.get("last_name", "")
    first_last = f"{first_name} {last_name}".strip()
    name = clerk_payload.get("name") or first_last or f"User {clerk_id[-8:]}"

    user = User(
        clerk_id=clerk_id,
        email=email,
        name=name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by their UUID string."""
    return await db.scalar(select(User).where(User.id == user_id))
