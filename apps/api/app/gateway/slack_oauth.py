"""
Slack OAuth 2.0 flow — "Connect Slack" onboarding.

Endpoints
--------
GET /api/slack/install
    Redirect the user to Slack's OAuth authorize page.
    Query params: ``employee_id`` (UUID), ``org_id`` (UUID).

GET /api/slack/oauth/callback
    Handle the OAuth redirect from Slack.  Exchanges the temporary code for
    a bot token, encrypts it, stores it on the employee record, and redirects
    the browser back to the dashboard.

Identity modes
--------------
- **shared** (legacy): One global Slack app for all employees.  Uses
  ``SLACK_CLIENT_ID`` / ``SLACK_CLIENT_SECRET`` from settings.
- **per_employee** (Pattern A): Each employee has its own Slack app
  identity via a pre-provisioned ``SlackAppSlot``.  The slot holds its
  own ``client_id`` / ``client_secret`` for OAuth.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadData, URLSafeTimedSerializer
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.security import decrypt_token, encrypt_token

# Ensure all model modules are imported before using relationship loaders
import app.auth.models  # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.employees.models  # noqa: F401
import app.organizations.models  # noqa: F401
import app.agent.tools.mcp.models  # noqa: F401
import app.gateway.models  # noqa: F401

from app.employees.models import Employee
from app.gateway.models import SlackAppSlot

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

# How long the OAuth state token is valid (seconds).
_STATE_MAX_AGE = 600  # 10 minutes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_state_secret() -> str:
    """Return a secret key for signing OAuth state tokens."""
    return settings.encryption_key or settings.clerk_secret_key or "change-me"


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_get_state_secret(), salt="slack-oauth-state")


def _encode_oauth_state(employee_id: UUID, org_id: UUID, redirect_to: str | None = None) -> str:
    """Create a short-lived signed token for the OAuth state parameter."""
    payload: dict[str, str] = {
        "employee_id": str(employee_id),
        "org_id": str(org_id),
    }
    if redirect_to:
        payload["redirect_to"] = redirect_to
    return _get_serializer().dumps(payload)


def _decode_oauth_state(state: str) -> dict | None:
    """Decode and validate the OAuth state token.  Returns the payload dict
    or ``None`` if it is expired / tampered with / missing fields."""
    try:
        payload = _get_serializer().loads(state, max_age=_STATE_MAX_AGE)
    except BadData:
        logger.warning("Slack OAuth state token is invalid or expired")
        return None

    if not isinstance(payload, dict):
        return None

    required = {"employee_id", "org_id"}
    if not required.issubset(payload.keys()):
        logger.warning("Slack OAuth state token missing required fields")
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


async def _load_employee_with_slot(
    session, emp_uuid: UUID, org_uuid: UUID
) -> tuple[Employee | None, SlackAppSlot | None]:
    """Load an employee and its assigned Slack app slot (if any)."""
    emp = await session.scalar(
        select(Employee)
        .where(Employee.id == emp_uuid, Employee.org_id == org_uuid)
        .options(selectinload(Employee.slack_slot))
    )
    if emp is None:
        return None, None
    return emp, emp.slack_slot


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/install")
async def slack_install(
    request: Request,
    employee_id: str = Query(..., description="Employee UUID"),
    org_id: str = Query(..., description="Organization UUID"),
    redirect_to: str | None = Query(None, description="URL to redirect back to after callback"),
) -> RedirectResponse:
    """Redirect the browser to Slack's OAuth authorize page.

    The ``employee_id`` and ``org_id`` are baked into a signed state
    parameter so the callback can associate the token with the right
    employee.

    In **per_employee** mode the authorize URL is built from the employee's
    assigned ``SlackAppSlot`` rather than the global settings.
    """
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

    async with async_session_factory() as session:
        emp, slot = await _load_employee_with_slot(session, emp_uuid, org_uuid)

    if emp is None:
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Employee not found.",
            redirect_to=redirect_to,
        )

    actual_redirect_to = redirect_to or f"{settings.frontend_url.rstrip('/')}/dashboard/{emp_uuid}"
    state = _encode_oauth_state(emp_uuid, org_uuid, actual_redirect_to)
    scope = ",".join(_SLACK_BOT_SCOPES)

    if settings.slack_identity_mode == "per_employee":
        # ---- Pattern A: per-slot OAuth -----------------------------------
        if slot is None:
            return _frontend_redirect(
                employee_id,
                success=False,
                detail="No Slack app slot assigned — capacity may be full.",
                redirect_to=redirect_to,
            )
        client_id = slot.client_id
        redirect_uri = settings.slack_oauth_redirect_uri
        if not redirect_uri or "<YOUR-RAILWAY-API-DOMAIN>" in redirect_uri:
            base_url = str(request.base_url).rstrip("/")
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme
            if proto == "https" and base_url.startswith("http://"):
                base_url = base_url.replace("http://", "https://")
            redirect_uri = f"{base_url}/api/slack/oauth/callback"
    else:
        # ---- Shared mode (legacy): global app ----------------------------
        if not settings.slack_client_id:
            logger.error("Slack OAuth is not configured (missing client_id).")
            return _frontend_redirect(
                employee_id,
                success=False,
                detail="Slack integration is not configured on this server.",
                redirect_to=redirect_to,
            )
        client_id = settings.slack_client_id
        redirect_uri = settings.slack_oauth_redirect_uri
        if not redirect_uri or "<YOUR-RAILWAY-API-DOMAIN>" in redirect_uri:
            base_url = str(request.base_url).rstrip("/")
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme
            if proto == "https" and base_url.startswith("http://"):
                base_url = base_url.replace("http://", "https://")
            redirect_uri = f"{base_url}/api/slack/oauth/callback"

    authorize_url = (
        f"{_SLACK_AUTHORIZE_URL}"
        f"?client_id={client_id}"
        f"&scope={scope}"
        f"&state={state}"
        f"&redirect_uri={redirect_uri}"
    )

    logger.info(
        "Redirecting to Slack OAuth for employee %s (org %s, mode=%s)",
        employee_id,
        org_id,
        settings.slack_identity_mode,
    )
    return RedirectResponse(authorize_url, status_code=303)


@router.get("/oauth/callback")
async def slack_oauth_callback(
    request: Request,
    code: str = Query(..., description="Temporary OAuth code from Slack"),
    state: str = Query(..., description="State parameter echoed back by Slack"),
) -> RedirectResponse:
    """Handle the OAuth redirect from Slack.

    1. Validates the state JWT to recover employee / org.
    2. Exchanges the ``code`` for a bot token via Slack's API.
    3. Encrypts and stores the token on the employee record.
    4. Redirects the browser back to the employee's dashboard page.

    In **per_employee** mode the exchange uses the slot's client secret
    rather than the global one, and persists workspace metadata.
    """
    # ---- 1. Validate state --------------------------------------------------
    payload = _decode_oauth_state(state)
    if payload is None:
        return RedirectResponse(
            f"{settings.frontend_url.rstrip('/')}/dashboard?slack=error&reason=invalid_state",
            status_code=303,
        )

    employee_id = payload["employee_id"]
    org_id = payload["org_id"]
    redirect_to = payload.get("redirect_to")

    async with async_session_factory() as session:
        emp, slot = await _load_employee_with_slot(session, UUID(employee_id), UUID(org_id))

    if emp is None:
        return _frontend_redirect(
            employee_id,
            success=False,
            detail="Employee no longer exists.",
            redirect_to=redirect_to,
        )

    # Determine which credentials to use
    if settings.slack_identity_mode == "per_employee":
        if slot is None:
            return _frontend_redirect(
                employee_id,
                success=False,
                detail="No Slack app slot assigned.",
                redirect_to=redirect_to,
            )
        oauth_client_id = slot.client_id
        oauth_client_secret = decrypt_token(slot.client_secret_enc)
        oauth_redirect_uri = settings.slack_oauth_redirect_uri
        if not oauth_redirect_uri or "<YOUR-RAILWAY-API-DOMAIN>" in oauth_redirect_uri:
            base_url = str(request.base_url).rstrip("/")
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme
            if proto == "https" and base_url.startswith("http://"):
                base_url = base_url.replace("http://", "https://")
            oauth_redirect_uri = f"{base_url}/api/slack/oauth/callback"
    else:
        if not settings.slack_client_id or not settings.slack_client_secret:
            logger.error("Slack OAuth config incomplete — cannot exchange code.")
            return _frontend_redirect(
                employee_id,
                success=False,
                detail="Slack integration is not fully configured.",
                redirect_to=redirect_to,
            )
        oauth_client_id = settings.slack_client_id
        oauth_client_secret = settings.slack_client_secret
        oauth_redirect_uri = settings.slack_oauth_redirect_uri
        if not oauth_redirect_uri or "<YOUR-RAILWAY-API-DOMAIN>" in oauth_redirect_uri:
            base_url = str(request.base_url).rstrip("/")
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme
            if proto == "https" and base_url.startswith("http://"):
                base_url = base_url.replace("http://", "https://")
            oauth_redirect_uri = f"{base_url}/api/slack/oauth/callback"

    # ---- 2. Exchange code for token -----------------------------------------
    try:
        client = AsyncWebClient()
        oauth_response = await client.oauth_v2_access(
            client_id=oauth_client_id,
            client_secret=oauth_client_secret,
            code=code,
            redirect_uri=oauth_redirect_uri,
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

    # ---- 3. Store encrypted token + workspace metadata -----------------------
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

        # Persist workspace metadata from OAuth response
        team = oauth_response.get("team", {})
        emp.slack_team_id = team.get("id")
        emp.slack_team_name = team.get("name")

        # Auto-activate the employee so the gateway picks it up
        if emp.status == "inactive":
            emp.status = "active"

        await session.commit()

    logger.info(
        "Slack OAuth complete — token stored for employee %s (team: %s, mode=%s)",
        employee_id,
        oauth_response.get("team", {}).get("name", "unknown"),
        settings.slack_identity_mode,
    )

    # ---- 4. Redirect to dashboard -------------------------------------------
    return _frontend_redirect(employee_id, success=True, redirect_to=redirect_to)
