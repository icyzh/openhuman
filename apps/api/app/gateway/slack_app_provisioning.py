"""Slot assignment, release, and manifest helpers for Pattern A Slack provisioning.

Pattern A gives each AI employee its own Slack app identity.  This module
manages the pre-provisioned slot pool: assigning available slots to employees
at creation time, releasing them on deletion, and building parameterized
manifests for display-name updates.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token, encrypt_token
from app.employees.models import Employee
from app.gateway.models import SlackAppSlot

# Path to the manifest template, relative to this file
_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "slack_manifest.json"


def _load_manifest_template() -> dict:
    """Load the base Slack manifest template from disk."""
    with open(_MANIFEST_PATH) as f:
        return json.load(f)


def build_manifest(employee_name: str) -> dict:
    """Return a Slack app manifest with display_name set to *employee_name*.

    Loads the shared ``slack_manifest.json`` template and injects the
    employee-specific display name and description so each app feels like a
    distinct team member.
    """
    manifest = _load_manifest_template()
    manifest.setdefault("display_information", {})["name"] = employee_name
    manifest.setdefault("display_information", {})[
        "description"
    ] = f"AI employee — {employee_name}"
    manifest.setdefault("features", {}).setdefault("bot_user", {})[
        "display_name"
    ] = employee_name
    return manifest


async def assign_slot_to_employee(
    db: AsyncSession, employee: Employee
) -> SlackAppSlot | None:
    """Assign an available slot to *employee* and return it.

    Uses ``SELECT ... FOR UPDATE`` to safely claim a slot under concurrent
    requests.  Returns ``None`` when the pool is exhausted.
    """
    result = await db.execute(
        select(SlackAppSlot)
        .where(SlackAppSlot.status == "available")
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    slot: SlackAppSlot | None = result.scalars().first()
    if slot is None:
        return None

    slot.status = "assigned"
    slot.employee_id = employee.id
    slot.assigned_at = datetime.now(timezone.utc)
    employee.slack_slot_id = slot.id

    await db.flush()
    return slot


async def release_slot(
    db: AsyncSession, employee: Employee, *, revoke_token: bool = True
) -> None:
    """Release the employee's slot back to the available pool.

    Clears Slack-related fields on the employee row.  Set *revoke_token* to
    ``False`` to keep the workspace bot token in place (e.g. for a soft
    deactivation rather than permanent delete).
    """
    if employee.slack_slot_id is None:
        return

    slot_result = await db.execute(
        select(SlackAppSlot).where(SlackAppSlot.id == employee.slack_slot_id)
    )
    slot: SlackAppSlot | None = slot_result.scalars().first()
    if slot is not None:
        slot.status = "available"
        slot.employee_id = None
        slot.assigned_at = None

    employee.slack_slot_id = None
    employee.slack_team_id = None
    employee.slack_team_name = None
    employee.slack_bot_user_id = None
    if revoke_token:
        employee.slack_token_enc = None

    await db.flush()


async def get_slot_credentials(
    db: AsyncSession, slot_id: UUID
) -> tuple[str, str, str] | None:
    """Decrypt and return ``(client_id, client_secret, app_token)`` for a slot.

    Returns ``None`` if the slot does not exist.
    """
    result = await db.execute(
        select(SlackAppSlot).where(SlackAppSlot.id == slot_id)
    )
    slot: SlackAppSlot | None = result.scalars().first()
    if slot is None:
        return None
    return (
        slot.client_id,
        decrypt_token(slot.client_secret_enc),
        decrypt_token(slot.app_token_enc),
    )


async def count_available_slots(db: AsyncSession) -> int:
    """Return the number of currently available (unassigned) slots."""
    result = await db.execute(
        select(SlackAppSlot).where(SlackAppSlot.status == "available")
    )
    return len(result.scalars().all())


async def insert_slot(
    db: AsyncSession,
    *,
    slack_app_id: str,
    client_id: str,
    client_secret: str,
    app_token: str,
) -> SlackAppSlot:
    """Insert a new pre-provisioned slot with encrypted credentials.

    Used by the ops provisioning script.
    """
    slot = SlackAppSlot(
        slack_app_id=slack_app_id,
        client_id=client_id,
        client_secret_enc=encrypt_token(client_secret),
        app_token_enc=encrypt_token(app_token),
        status="available",
    )
    db.add(slot)
    await db.flush()
    return slot
