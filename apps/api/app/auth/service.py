import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import UpdateUserRequest
from app.organizations.schemas import CreateOrganizationRequest
from app.organizations.service import create_org

logger = logging.getLogger(__name__)


async def get_or_create_user(db: AsyncSession, clerk_id: str, clerk_payload: dict) -> User:
    """Look up a local User by Clerk ID, creating one on first login.

    On first login a default "My Organization" is also provisioned so the
    dashboard has something to show immediately.
    """
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
        onboarding_completed=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Auto-create a default organization for every new user
    try:
        await create_org(
            db,
            user.id,
            CreateOrganizationRequest(name="My Organization"),
        )
    except Exception:
        logger.exception(
            "Failed to create default org for user %s (non-blocking)", user.id
        )

    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by their UUID string."""
    return await db.scalar(select(User).where(User.id == user_id))


async def update_user(
    db: AsyncSession, user: User, data: UpdateUserRequest
) -> User:
    """Update the current user's profile fields."""
    user.onboarding_completed = data.onboarding_completed
    await db.commit()
    await db.refresh(user)
    return user
