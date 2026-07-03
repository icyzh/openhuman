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

    auth_options: dict = {"secret_key": settings.clerk_secret_key}
    if settings.clerk_jwt_key:
        auth_options["jwt_key"] = settings.clerk_jwt_key
    # Only enforce authorized_parties when explicitly configured.
    # An empty / unset list means "accept any party" (dev-friendly default).
    if settings.clerk_authorized_parties_list:
        auth_options["authorized_parties"] = settings.clerk_authorized_parties_list

    request_state = authenticate_request(
        request,
        AuthenticateRequestOptions(**auth_options),  # type: ignore[arg-type]
    )

    if not request_state.is_signed_in:
        reason = request_state.message or "Invalid token"
        raise _unauthorized(
            f"Clerk: {reason}"
            f" (secret={settings.clerk_secret_key[:8] if settings.clerk_secret_key else 'MISSING'}…"
            f" parties={settings.clerk_authorized_parties_list})"
        )

    clerk_user_id: str | None = request_state.payload.get("sub")
    if not clerk_user_id:
        raise _unauthorized("Token missing sub claim")

    user = await get_or_create_user(db, clerk_user_id, request_state.payload)
    if not user.is_active:
        raise _unauthorized("User not found")

    return user
