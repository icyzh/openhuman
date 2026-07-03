from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.channel_assignments.schemas import ChannelAssignmentResponse
from app.core.config import settings
from app.core.security import decrypt_token, encrypt_token
from app.employees.models import Employee
from app.employees.schemas import (
    CreateEmployeeRequest,
    EmployeeResponse,
    UpdateEmployeeRequest,
)
from app.gateway.models import SlackAppSlot
from app.gateway.slack_app_provisioning import (
    assign_slot_to_employee,
    release_slot,
    update_slack_app_manifest,
)
from app.memory.service import (
    add_user_to_tenant,
    create_dataset,
    create_employee_user,
    forget_dataset,
    get_or_create_admin,
    grant_tenant_read,
    remember,
)
from app.organizations.models import Organization

logger = logging.getLogger(__name__)


def _build_employee_profile(emp: Employee) -> str:
    """Serialize employee identity fields to JSON for Cognee profile seed."""
    return json.dumps({
        "name": emp.name,
        "role": emp.role,
        "employee_type": emp.employee_type,
        "personality": emp.personality,
        "specialization": emp.specialization,
    })

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DuplicateEmployeeTypeError(Exception):
    """Raised when creating/updating an employee to a type already used by the org."""


class PoolExhaustionError(Exception):
    """Raised when the Slack app slot pool has no available slots."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_org(db: AsyncSession, org_id: UUID, user_id: UUID) -> Organization | None:
    """Return the org only if it belongs to user_id."""
    return await db.scalar(
        select(Organization).where(
            Organization.id == org_id, Organization.owner_id == user_id
        )
    )


async def _get_employee_with_assignments(
    db: AsyncSession, emp_id: UUID, org_id: UUID
) -> Employee | None:
    """Fetch an employee with channel_assignments eagerly loaded."""
    return await db.scalar(
        select(Employee)
        .where(Employee.id == emp_id, Employee.org_id == org_id)
        .options(selectinload(Employee.channel_assignments))
    )


def _to_response(emp: Employee) -> EmployeeResponse:
    """Build EmployeeResponse from ORM object, masking raw tokens."""
    return EmployeeResponse(
        id=emp.id,
        org_id=emp.org_id,
        name=emp.name,
        employee_type=emp.employee_type,
        role=emp.role,
        personality=emp.personality,
        specialization=emp.specialization,
        duties=emp.duties,
        memory_policy=emp.memory_policy,
        escalation_policy=emp.escalation_policy,
        mcp_connections=emp.mcp_connections,
        status=emp.status,
        has_discord_token=emp.discord_token_enc is not None,
        has_slack_token=emp.slack_token_enc is not None,
        has_slack_slot=emp.slack_slot_id is not None,
        slack_team_name=emp.slack_team_name,
        slack_bot_user_id=emp.slack_bot_user_id,
        cognee_user_id=emp.cognee_user_id,
        cognee_dataset_name=emp.cognee_dataset_name,
        channel_assignments=[
            ChannelAssignmentResponse.model_validate(ca, from_attributes=True)
            for ca in (emp.channel_assignments or [])
        ],
        created_at=emp.created_at,
        updated_at=emp.updated_at,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_employee(
    db: AsyncSession, org_id: UUID, user_id: UUID, data: CreateEmployeeRequest
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None

    # Enforce one employee per type per organization
    if data.employee_type:
        existing = await db.scalar(
            select(Employee).where(
                Employee.org_id == org_id,
                Employee.employee_type == data.employee_type,
            )
        )
        if existing is not None:
            raise DuplicateEmployeeTypeError(
                f"An employee of type '{data.employee_type}' already exists in this organization."
            )

    emp = Employee(
        org_id=org_id,
        name=data.name,
        role=data.role,
        personality=data.personality,
        specialization=data.specialization,
        employee_type=data.employee_type,
        duties=data.duties,
        memory_policy=data.memory_policy,
    )
    db.add(emp)
    await db.flush()

    # Pattern A: assign a Slack app slot so this employee can get its own identity
    if settings.slack_identity_mode == "per_employee":
        slot = await assign_slot_to_employee(db, emp)
        if slot is None:
            await db.rollback()
            raise PoolExhaustionError(
                "No available Slack app slots. Provision more slots before "
                "creating additional employees in per_employee mode."
            )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "ix_employees_org_id_employee_type" in str(exc):
            raise DuplicateEmployeeTypeError(
                f"An employee of type '{data.employee_type}' already exists in this organization."
            ) from exc
        raise

    # ── Cognee provisioning (best-effort, only if org has tenant) ──────
    if org.cognee_tenant_id:
        try:
            admin = await get_or_create_admin()
            cognee_user = await create_employee_user(
                org.cognee_tenant_id, emp.name
            )
            await add_user_to_tenant(
                cognee_user["id"], org.cognee_tenant_id, admin["id"]
            )
            dataset = await create_dataset(
                f"employee-{emp.id}", cognee_user["id"]
            )
            await grant_tenant_read(
                dataset["id"], org.cognee_tenant_id, cognee_user["id"]
            )

            # Seed employee profile
            profile = _build_employee_profile(emp)
            await remember(
                profile,
                f"employee-{emp.id}",
                cognee_user["id"],
                dataset_id=dataset["id"],
                background=True,
            )

            # Persist Cognee IDs on employee row
            emp.cognee_user_id = cognee_user["id"]
            emp.cognee_user_name = cognee_user["email"]
            emp.cognee_dataset_id = dataset["id"]
            emp.cognee_dataset_name = dataset["name"]
            await db.commit()
        except Exception:
            logger.exception(
                "Cognee employee provisioning failed for emp %s "
                "(non-blocking)",
                emp.id,
            )
    # ── End Cognee ──────────────────────────────────────────────────────

    # Re-fetch with relationships
    emp = await _get_employee_with_assignments(db, emp.id, org_id)  # type: ignore[assignment]
    return _to_response(emp)  # type: ignore[arg-type]


async def get_employee(
    db: AsyncSession, org_id: UUID, emp_id: UUID, user_id: UUID
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    emp = await _get_employee_with_assignments(db, emp_id, org_id)
    if emp is None:
        return None
    return _to_response(emp)


async def list_employees(
    db: AsyncSession, org_id: UUID, user_id: UUID
) -> list[EmployeeResponse] | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    result = await db.execute(
        select(Employee)
        .where(Employee.org_id == org_id)
        .options(selectinload(Employee.channel_assignments))
        .order_by(Employee.created_at.desc())
    )
    return [_to_response(e) for e in result.scalars().all()]


_ALLOWED_STATUSES = {"active", "inactive", "suspended"}


async def update_employee(
    db: AsyncSession, org_id: UUID, emp_id: UUID, user_id: UUID, data: UpdateEmployeeRequest
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    emp = await _get_employee_with_assignments(db, emp_id, org_id)
    if emp is None:
        return None

    # If employee_type is being changed, check for conflicts
    if data.employee_type is not None and data.employee_type != emp.employee_type:
        existing = await db.scalar(
            select(Employee).where(
                Employee.org_id == org_id,
                Employee.employee_type == data.employee_type,
                Employee.id != emp_id,
            )
        )
        if existing is not None:
            raise DuplicateEmployeeTypeError(
                f"An employee of type '{data.employee_type}' already exists in this organization."
            )

    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        if field == "status" and value not in _ALLOWED_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_ALLOWED_STATUSES)}"
            )
        setattr(emp, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "ix_employees_org_id_employee_type" in str(exc):
            raise DuplicateEmployeeTypeError(
                f"An employee of type '{data.employee_type}' already exists in this organization."
            ) from exc
        raise

    # ── Re-seed Cognee profile if identity fields changed ───────────────
    cognee_changed = any(
        field in update_data
        for field in (
            "name", "role", "employee_type",
            "personality", "specialization",
        )
    )
    if cognee_changed and emp.cognee_user_id and emp.cognee_dataset_name:
        try:
            profile = _build_employee_profile(emp)
            await remember(
                profile,
                emp.cognee_dataset_name,
                emp.cognee_user_id,
                dataset_id=emp.cognee_dataset_id,
                background=True,
            )
        except Exception:
            logger.exception(
                "Cognee profile re-seed failed for emp %s (non-blocking)",
                emp.id,
            )
    # ── End Cognee ──────────────────────────────────────────────────────

    # ── Slack app manifest rename (best-effort) ──────────────────────────
    if settings.slack_identity_mode == "per_employee" and "name" in update_data:
        try:
            await update_slack_app_manifest(db, emp.id, update_data["name"])
        except Exception:
            logger.exception(
                "Slack app manifest rename failed for emp %s (non-blocking)",
                emp.id,
            )
    # ── End Slack app manifest rename ────────────────────────────────────

    emp = await _get_employee_with_assignments(db, emp_id, org_id)  # type: ignore[arg-type]
    return _to_response(emp)  # type: ignore[arg-type]


async def delete_employee(
    db: AsyncSession, org_id: UUID, emp_id: UUID, user_id: UUID
) -> bool:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return False
    emp = await db.scalar(
        select(Employee).where(Employee.id == emp_id, Employee.org_id == org_id)
    )
    if emp is None:
        return False

    # Pattern A: release the Slack app slot back to the pool
    if settings.slack_identity_mode == "per_employee":
        await release_slot(db, emp)

    # ── Best-effort Cognee cleanup ──────────────────────────────────────
    if emp.cognee_dataset_name:
        try:
            await forget_dataset(emp.cognee_dataset_name)
        except Exception:
            logger.exception(
                "Cognee forget_dataset failed during employee delete %s",
                emp.id,
            )
    # ─────────────────────────────────────────────────────────────────────

    await db.delete(emp)
    await db.commit()
    return True


async def store_discord_token(
    db: AsyncSession, org_id: UUID, emp_id: UUID, user_id: UUID, token: str
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    emp = await _get_employee_with_assignments(db, emp_id, org_id)
    if emp is None:
        return None
    emp.discord_token_enc = encrypt_token(token)
    await db.commit()
    emp = await _get_employee_with_assignments(db, emp_id, org_id)  # type: ignore[assignment]
    return _to_response(emp)  # type: ignore[arg-type]


async def store_slack_token(
    db: AsyncSession, org_id: UUID, emp_id: UUID, user_id: UUID, token: str
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    emp = await _get_employee_with_assignments(db, emp_id, org_id)
    if emp is None:
        return None
    emp.slack_token_enc = encrypt_token(token)
    await db.commit()
    emp = await _get_employee_with_assignments(db, emp_id, org_id)  # type: ignore[assignment]
    return _to_response(emp)  # type: ignore[arg-type]


async def update_status(
    db: AsyncSession, org_id: UUID, emp_id: UUID, user_id: UUID, new_status: str
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    emp = await _get_employee_with_assignments(db, emp_id, org_id)
    if emp is None:
        return None
    emp.status = new_status
    await db.commit()
    emp = await _get_employee_with_assignments(db, emp_id, org_id)  # type: ignore[assignment]
    return _to_response(emp)  # type: ignore[arg-type]


async def get_employee_raw(
    db: AsyncSession, emp_id: UUID
) -> Employee | None:
    """Fetch raw Employee ORM object (used by gateway to read encrypted tokens)."""
    return await db.scalar(select(Employee).where(Employee.id == emp_id))


async def get_active_employees_with_tokens(db: AsyncSession) -> list[Employee]:
    """Return all active employees that have at least one bot token. Used by gateway."""
    result = await db.execute(
        select(Employee)
        .where(
            Employee.status == "active",
            (Employee.discord_token_enc.is_not(None)) | (Employee.slack_token_enc.is_not(None)),
        )
        .options(selectinload(Employee.slack_slot))
    )
    return list(result.scalars().all())


def decrypt_discord_token(emp: Employee) -> str | None:
    """Decrypt the Discord token for a given employee. Returns None if not set."""
    if emp.discord_token_enc is None:
        return None
    return decrypt_token(emp.discord_token_enc)


def decrypt_slack_token(emp: Employee) -> str | None:
    """Decrypt the Slack token for a given employee. Returns None if not set."""
    if emp.slack_token_enc is None:
        return None
    return decrypt_token(emp.slack_token_enc)


async def update_slack_slot_credentials(
    db: AsyncSession,
    org_id: UUID,
    emp_id: UUID,
    user_id: UUID,
    client_id: str | None = None,
    client_secret: str | None = None,
    app_token: str | None = None,
) -> EmployeeResponse | None:
    org = await _get_org(db, org_id, user_id)
    if org is None:
        return None
    emp = await db.scalar(
        select(Employee)
        .where(Employee.id == emp_id, Employee.org_id == org_id)
    )
    if emp is None or emp.slack_slot_id is None:
        return None

    slot = await db.scalar(
        select(SlackAppSlot)
        .where(SlackAppSlot.id == emp.slack_slot_id)
    )
    if slot is None:
        return None

    if client_id:
        slot.client_id = client_id
    if client_secret:
        slot.client_secret_enc = encrypt_token(client_secret)
    if app_token:
        slot.app_token_enc = encrypt_token(app_token)

    await db.commit()

    emp = await _get_employee_with_assignments(db, emp_id, org_id)
    return _to_response(emp)
