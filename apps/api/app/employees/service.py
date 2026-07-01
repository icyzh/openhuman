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
from app.gateway.slack_app_provisioning import assign_slot_to_employee, release_slot
from app.organizations.models import Organization

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DuplicateEmployeeTypeError(Exception):
    """Raised when creating/updating an employee to a type already used by the org."""


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
        await assign_slot_to_employee(db, emp)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "ix_employees_org_id_employee_type" in str(exc):
            raise DuplicateEmployeeTypeError(
                f"An employee of type '{data.employee_type}' already exists in this organization."
            ) from exc
        raise
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

    for field, value in data.model_dump(exclude_none=True).items():
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
