"""Reusable MCP OAuth 2.0 helper — install redirect + code exchange + token refresh.

Generalizes the Slack OAuth pattern (`app/gateway/slack_oauth.py`) so every
OAuth-based MCP connector shares the same plumbing:

* ``build_authorize_url`` — redirect the browser to the provider's consent page.
* ``exchange_code`` — trade the temporary code for access + refresh tokens.
* ``refresh_access_token`` — lazily refresh an expired OAuth2 access token.
* Signed ``state`` parameter — ties the OAuth callback back to the right
  employee, org, and connector without a server-side session.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING
from urllib.parse import quote_plus, urlencode
from uuid import UUID

import httpx
from fastapi.responses import RedirectResponse
from itsdangerous import BadData, URLSafeTimedSerializer

from app.core.config import settings
from app.core.security import decrypt_token, encrypt_token

if TYPE_CHECKING:
    from app.agent.tools.mcp.connectors.spec import ConnectorSpec
    from app.agent.tools.mcp.models import McpConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How long the OAuth state token is valid (seconds).
_STATE_MAX_AGE = 600  # 10 minutes

# ---------------------------------------------------------------------------
# Signed state helpers
# ---------------------------------------------------------------------------


def _get_state_secret() -> str:
    """Return a secret key for signing OAuth state tokens."""
    return settings.encryption_key or settings.clerk_secret_key or "change-me"


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_get_state_secret(), salt="mcp-oauth-state")


def _encode_oauth_state(
    employee_id: UUID,
    org_id: UUID,
    connector_slug: str,
    redirect_to: str | None = None,
) -> str:
    """Create a short-lived signed token for the OAuth ``state`` parameter.

    Survives the round-trip through the provider so the callback can recover
    *who* initiated the flow and for *which connector* — no server-side
    session storage needed.
    """
    payload: dict[str, str] = {
        "employee_id": str(employee_id),
        "org_id": str(org_id),
        "connector_slug": connector_slug,
    }
    if redirect_to:
        payload["redirect_to"] = redirect_to
    return _get_serializer().dumps(payload)


def _decode_oauth_state(state: str) -> dict | None:
    """Decode and validate the OAuth state token.

    Returns the payload dict or ``None`` if the token is expired, tampered
    with, or has missing fields.
    """
    try:
        payload = _get_serializer().loads(state, max_age=_STATE_MAX_AGE)
    except BadData:
        logger.warning("MCP OAuth state token is invalid or expired")
        return None

    if not isinstance(payload, dict):
        return None

    required = {"employee_id", "org_id", "connector_slug"}
    if not required.issubset(payload.keys()):
        logger.warning("MCP OAuth state token missing required fields")
        return None

    return payload


# ---------------------------------------------------------------------------
# Public OAuth helpers
# ---------------------------------------------------------------------------


def build_authorize_url(
    spec: ConnectorSpec,
    employee_id: UUID,
    org_id: UUID,
    redirect_to: str | None = None,
) -> str:
    """Build the full OAuth2 authorize URL for *spec* with JWT-encoded state.

    Raises :class:`ValueError` when the connector spec or server settings
    are incomplete (missing ``authorize_url``, unconfigured client id,
    missing redirect URI).
    """
    if not spec.authorize_url:
        raise ValueError(f"Connector '{spec.slug}' has no authorize_url configured.")

    creds = settings.mcp_oauth_credentials.get(spec.slug)
    if not creds or not creds["client_id"]:
        raise ValueError(
            f"OAuth client_id for '{spec.slug}' is not configured. "
            f"Set {spec.slug.upper()}_CLIENT_ID in the environment."
        )

    if not settings.mcp_oauth_redirect_uri:
        raise ValueError("MCP_OAUTH_REDIRECT_URI is not configured.")

    state = _encode_oauth_state(employee_id, org_id, spec.slug, redirect_to)

    params: dict[str, str] = {
        "client_id": creds["client_id"],
        "state": state,
        "redirect_uri": settings.mcp_oauth_redirect_uri,
        "response_type": "code",
    }
    scope = " ".join(spec.default_scopes) if spec.default_scopes else ""
    if scope:
        params["scope"] = scope

    return f"{spec.authorize_url}?{urlencode(params)}"


async def exchange_code(
    spec: ConnectorSpec,
    code: str,
) -> dict:
    """Exchange a temporary OAuth2 authorization ``code`` for tokens.

    Returns the full token-response dict (``access_token``,
    ``refresh_token``, ``expires_in``, ``scope``, …).

    Raises :class:`ValueError` on configuration problems or missing fields
    in the response; raises :class:`httpx.HTTPError` on transport / HTTP
    errors.
    """
    if not spec.token_url:
        raise ValueError(f"Connector '{spec.slug}' has no token_url configured.")

    creds = settings.mcp_oauth_credentials.get(spec.slug)
    if not creds or not creds["client_id"]:
        raise ValueError(
            f"OAuth credentials for '{spec.slug}' are not configured."
        )

    if not settings.mcp_oauth_redirect_uri:
        raise ValueError("MCP_OAUTH_REDIRECT_URI is not configured.")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.mcp_oauth_redirect_uri,
    }

    headers: dict[str, str] = {"Accept": "application/json"}

    if spec.token_auth_method == "basic":
        raw = f"{creds['client_id']}:{creds['client_secret']}"
        headers["Authorization"] = f"Basic {base64.b64encode(raw.encode()).decode()}"
    else:
        payload["client_id"] = creds["client_id"]
        payload["client_secret"] = creds["client_secret"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            spec.token_url,
            data=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    if "access_token" not in data:
        raise ValueError(
            f"Token response from '{spec.slug}' missing access_token: "
            f"keys={list(data.keys())}"
        )

    return data


async def refresh_access_token(
    spec: ConnectorSpec,
    connection: McpConnection,
) -> str | None:
    """Attempt to refresh an expired OAuth2 access token using a stored
    refresh token.

    On success the *connection* record is updated in-place (caller must
    still commit the DB session).  Returns the new access-token string,
    or ``None`` if refresh is not possible (no refresh token stored,
    connector doesn't support refresh, or the provider rejected the
    attempt).
    """
    if not connection.oauth_refresh_token_enc:
        logger.debug("No refresh token stored for connection %s", connection.id)
        return None

    if not spec.token_url:
        logger.warning("Connector '%s' has no token_url for refresh", spec.slug)
        return None

    creds = settings.mcp_oauth_credentials.get(spec.slug)
    if not creds:
        logger.warning("No OAuth credentials configured for '%s'", spec.slug)
        return None

    refresh_token = decrypt_token(connection.oauth_refresh_token_enc)

    refresh_payload: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    refresh_headers: dict[str, str] = {"Accept": "application/json"}

    if spec.token_auth_method == "basic":
        raw = f"{creds['client_id']}:{creds['client_secret']}"
        refresh_headers["Authorization"] = f"Basic {base64.b64encode(raw.encode()).decode()}"
    else:
        refresh_payload["client_id"] = creds["client_id"]
        refresh_payload["client_secret"] = creds["client_secret"]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                spec.token_url,
                data=refresh_payload,
                headers=refresh_headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Token refresh failed for connection %s", connection.id)
        return None

    new_access_token: str | None = data.get("access_token")
    if not new_access_token:
        logger.warning(
            "Refresh response missing access_token for connection %s",
            connection.id,
        )
        return None

    # Rotate the stored secrets
    connection.credentials_enc = encrypt_token(new_access_token)
    if "refresh_token" in data:
        connection.oauth_refresh_token_enc = encrypt_token(data["refresh_token"])

    logger.info(
        "Refreshed OAuth token for connection %s (%s)", connection.id, spec.slug
    )
    return new_access_token


# ---------------------------------------------------------------------------
# Frontend redirect helper
# ---------------------------------------------------------------------------


def _frontend_redirect(
    employee_id: str,
    connector_slug: str,
    success: bool,
    detail: str = "",
    redirect_to: str | None = None,
) -> RedirectResponse:
    """Build a ``303 See Other`` redirect back to the frontend with
    ``mcp_oauth`` query parameters so the UI can show success / error."""
    base_url = redirect_to or settings.frontend_url
    separator = "&" if "?" in base_url else "?"
    status_str = "connected" if success else "error"
    url = (
        f"{base_url.rstrip('/')}{separator}"
        f"mcp_oauth={status_str}"
        f"&connector={quote_plus(connector_slug)}"
    )
    if not success:
        url += f"&reason={quote_plus(detail)}"
    url += f"&employee_id={quote_plus(employee_id)}"
    return RedirectResponse(url, status_code=303)
