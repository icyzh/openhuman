"""
Slack OAuth 2.0 flow — "Connect Slack" onboarding.

Endpoints
---------
GET /api/slack/install
    Redirect the user to Slack's OAuth authorize page.
    Query params: ``employee_id`` (UUID), ``org_id`` (UUID).

GET /api/slack/oauth/callback
    Handle the OAuth redirect from Slack.  Exchanges the temporary code for
    a bot token, encrypts it, stores it on the employee record, and redirects
    the browser back to the dashboard.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
from slack_sdk.web.async_client import AsyncWebClient

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.security import encrypt_token
from app.employees.models import Employee
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Slack OAuth scopes the bot needs to function (Socket Mode + messaging).
_SLACK_BOT_SCOPES = [
    "app_mentions:read",
    "channels:history",
    "groups:history",
    "chat:write",
    "chat:write.customize",
    "im:history",
    "im:write",
    "mpim:history",
    "mpim:write",
    "users:read",
]

_SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"

# How long the OAuth state parameter is valid (minutes).
_STATE_EXPIRE_MINUTES = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_oauth_state_jwt(employee_id: UUID, org_id: UUID, redirect_to: str | None = None) -> str:
    """Create a short-lived JWT for the OAuth state parameter."""
    from jose import jwt as jose_jwt

    now = datetime.now(UTC)
    payload = {
        "employee_id": str(employee_id),
        "org_id": str(org_id),
        "iat": now,
        "exp": now + timedelta(minutes=_STATE_EXPIRE_MINUTES),
        "purpose": "slack_oauth",
    }
    if redirect_to:
        payload["redirect_to"] = redirect_to
    return jose_jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def _decode_oauth_state(state: str) -> dict | None:
    """Decode and validate the OAuth state JWT.  Returns the payload dict
    or ``None`` if it is expired / tampered with / not for this purpose."""
    from jose import JWTError, jwt as jose_jwt

    try:
        payload = jose_jwt.decode(
            state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        logger.warning("Slack OAuth state JWT is invalid")
        return None

    if payload.get("purpose") != "slack_oauth":
        logger.warning("Slack OAuth state JWT has wrong purpose")
        return None

    return payload


def _frontend_redirect(
    employee_id: str,
    success: bool,
    detail: str = "",
    redirect_to: str | None = None,
) -> RedirectResponse:
    """Build a redirect back to the frontend or custom target URL with a ``slack`` query param
    indicating outcome."""
    base_url = redirect_to or settings.frontend_url
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url.rstrip('/')}{separator}slack={'connected' if success else 'error'}"
    if not success:
        from urllib.parse import quote_plus
        url += f"&reason={quote_plus(detail)}"
    url += f"&employee_id={employee_id}"
    return RedirectResponse(url, status_code=303)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/install")
async def slack_install(
    employee_id: str = Query(..., description="Employee UUID"),
    org_id: str = Query(..., description="Organization UUID"),
    redirect_to: str | None = Query(None, description="URL to redirect back to after callback"),
) -> RedirectResponse:
    """Redirect the browser to Slack's OAuth authorize page.

    The ``employee_id`` and ``org_id`` are baked into a signed state
    parameter so the callback can associate the token with the right
    employee.
    """
    # Validate config
    if not settings.slack_client_id or not settings.slack_oauth_redirect_uri:
        logger.error("Slack OAuth is not configured (missing client_id or redirect_uri).")
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Slack integration is not configured on this server.",
            redirect_to=redirect_to,
        )

    # Validate UUIDs
    try:
        emp_uuid = UUID(employee_id)
        org_uuid = UUID(org_id)
    except ValueError:
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Invalid employee or organization ID.",
            redirect_to=redirect_to,
        )

    # Verify the employee exists
    async with async_session_factory() as session:
        emp = await session.scalar(
            select(Employee).where(
                Employee.id == emp_uuid,
                Employee.org_id == org_uuid,
            )
        )
    if emp is None:
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Employee not found.",
            redirect_to=redirect_to,
        )

    state = _encode_oauth_state_jwt(emp_uuid, org_uuid, redirect_to)
    scope = ",".join(_SLACK_BOT_SCOPES)

    authorize_url = (
        f"{_SLACK_AUTHORIZE_URL}"
        f"?client_id={settings.slack_client_id}"
        f"&scope={scope}"
        f"&state={state}"
        f"&redirect_uri={settings.slack_oauth_redirect_uri}"
    )

    logger.info(
        "Redirecting to Slack OAuth for employee %s (org %s)",
        employee_id,
        org_id,
    )
    return RedirectResponse(authorize_url, status_code=303)


@router.get("/oauth/callback")
async def slack_oauth_callback(
    code: str = Query(..., description="Temporary OAuth code from Slack"),
    state: str = Query(..., description="State parameter echoed back by Slack"),
) -> RedirectResponse:
    """Handle the OAuth redirect from Slack.

    1. Validates the state JWT to recover employee / org.
    2. Exchanges the ``code`` for a bot token via Slack's API.
    3. Encrypts and stores the token on the employee record.
    4. Redirects the browser back to the employee's dashboard page.
    """
    # ---- 1. Validate state --------------------------------------------------
    payload = _decode_oauth_state(state)
    if payload is None:
        return RedirectResponse(
            f"{settings.frontend_url.rstrip('/')}/?slack=error&reason=invalid_state",
            status_code=303,
        )

    employee_id = payload["employee_id"]
    org_id = payload["org_id"]
    redirect_to = payload.get("redirect_to")

    # Verify config
    if not settings.slack_client_id or not settings.slack_client_secret:
        logger.error("Slack OAuth config incomplete — cannot exchange code.")
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Slack integration is not fully configured.",
            redirect_to=redirect_to,
        )

    # ---- 2. Exchange code for token -----------------------------------------
    try:
        client = AsyncWebClient()
        oauth_response = await client.oauth_v2_access(
            client_id=settings.slack_client_id,
            client_secret=settings.slack_client_secret,
            code=code,
            redirect_uri=settings.slack_oauth_redirect_uri,
        )
    except Exception as exc:
        logger.exception("Slack OAuth token exchange failed")
        return _frontend_redirect(
            employee_id,
            success=False,
            detail=f"Token exchange failed: {exc}",
            redirect_to=redirect_to,
        )

    if not oauth_response.get("ok"):
        error_detail = oauth_response.get("error", "unknown_error")
        logger.error("Slack OAuth returned error: %s", error_detail)
        return _frontend_redirect(
            employee_id,
            success=False,
            detail=f"Slack rejected the request: {error_detail}",
            redirect_to=redirect_to,
        )

    bot_token = oauth_response.get("access_token")
    if not bot_token:
        logger.error("Slack OAuth response missing access_token")
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Slack did not return a bot token.",
            redirect_to=redirect_to,
        )

    # ---- 3. Store encrypted token -------------------------------------------
    try:
        encrypted = encrypt_token(bot_token)
    except Exception as exc:
        logger.exception("Failed to encrypt Slack bot token")
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Internal encryption error.",
            redirect_to=redirect_to,
        )

    async with async_session_factory() as session:
        emp = await session.scalar(
            select(Employee).where(
                Employee.id == UUID(employee_id),
                Employee.org_id == UUID(org_id),
            )
        )
        if emp is None:
            return _frontend_redirect(
                employee_id,
                success=False,
                detail="Employee no longer exists.",
                redirect_to=redirect_to,
            )

        emp.slack_token_enc = encrypted
        await session.commit()

    logger.info(
        "Slack OAuth complete — token stored for employee %s (team: %s)",
        employee_id,
        oauth_response.get("team", {}).get("name", "unknown"),
    )

    # ---- 4. Redirect to dashboard -------------------------------------------
    return _frontend_redirect(employee_id, success=True, redirect_to=redirect_to)
