from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions

from app.auth.models import User
from app.auth.service import get_or_create_user
from app.core.config import settings
from app.core.database import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the Clerk session token and return the local User.

    On first login the local User row is created automatically by syncing
    the Clerk user profile.
    """
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    token = credentials.credentials

    request_state = authenticate_request(
        request,
        AuthenticateRequestOptions(
            secret_key=settings.clerk_secret_key,
            authorized_parties=settings.clerk_authorized_parties_list,
            jwt_key=settings.clerk_jwt_key,
        ),
    )

    if not request_state.is_signed_in:
        raise _unauthorized(request_state.message or "Invalid token")

    clerk_user_id: str | None = request_state.payload.get("sub")
    if not clerk_user_id:
        raise _unauthorized("Token missing sub claim")

    user = await get_or_create_user(db, clerk_user_id, request_state.payload)
    if not user.is_active:
        raise _unauthorized("User not found")

    return user
