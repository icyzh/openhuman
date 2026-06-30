from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract JWT from Authorization header, validate, and return the User.

    Raises 401 if the token is missing, expired, or belongs to a deleted user.
    """
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise _unauthorized()
        user_uuid = UUID(user_id)
    except JWTError:
        raise _unauthorized()
    except ValueError:
        raise _unauthorized()

    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None or not user.is_active:
        raise _unauthorized("User not found")

    return user
