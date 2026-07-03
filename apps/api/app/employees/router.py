from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.employees.schemas import (
    CreateEmployeeRequest,
    DiscordTokenRequest,
    EmployeeResponse,
    SlackTokenRequest,
    StatusRequest,
    UpdateEmployeeRequest,
    UpdateSlackSlotRequest,
)
from app.employees.service import (
    DuplicateEmployeeTypeError,
    create_employee,
    delete_employee,
    get_employee,
    list_employees,
    store_discord_token,
    store_slack_token,
    update_employee,
    update_slack_slot_credentials,
    update_status,
)

router = APIRouter(
    prefix="/api/organizations/{org_id}/employees",
    tags=["employees"],
)


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee_route(
    org_id: UUID,
    data: CreateEmployeeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    try:
        result = await create_employee(db, org_id, current_user.id, data)
    except DuplicateEmployeeTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return result


@router.get("", response_model=list[EmployeeResponse])
async def list_employees_route(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EmployeeResponse]:
    result = await list_employees(db, org_id, current_user.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return result


@router.get("/{emp_id}", response_model=EmployeeResponse)
async def get_employee_route(
    org_id: UUID,
    emp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    result = await get_employee(db, org_id, emp_id, current_user.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return result


@router.patch("/{emp_id}", response_model=EmployeeResponse)
async def update_employee_route(
    org_id: UUID,
    emp_id: UUID,
    data: UpdateEmployeeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    try:
        result = await update_employee(db, org_id, emp_id, current_user.id, data)
    except DuplicateEmployeeTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return result


@router.delete("/{emp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee_route(
    org_id: UUID,
    emp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await delete_employee(db, org_id, emp_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")


@router.put("/{emp_id}/discord", response_model=EmployeeResponse)
async def set_discord_token(
    org_id: UUID,
    emp_id: UUID,
    data: DiscordTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    """Store an encrypted Discord bot token for this employee."""
    result = await store_discord_token(db, org_id, emp_id, current_user.id, data.token)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return result


@router.put("/{emp_id}/slack", response_model=EmployeeResponse)
async def set_slack_token(
    org_id: UUID,
    emp_id: UUID,
    data: SlackTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    """Store an encrypted Slack bot token for this employee."""
    result = await store_slack_token(db, org_id, emp_id, current_user.id, data.token)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return result


@router.put("/{emp_id}/status", response_model=EmployeeResponse)
async def set_status(
    org_id: UUID,
    emp_id: UUID,
    data: StatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    """Activate or deactivate an employee."""
    allowed = {"active", "inactive", "suspended"}
    if data.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of {sorted(allowed)}",
        )
    result = await update_status(db, org_id, emp_id, current_user.id, data.status)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return result


@router.patch("/{emp_id}/slack-slot", response_model=EmployeeResponse)
async def patch_slack_slot_route(
    org_id: UUID,
    emp_id: UUID,
    data: UpdateSlackSlotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeResponse:
    """Update credentials of the Slack slot assigned to this employee."""
    result = await update_slack_slot_credentials(
        db,
        org_id,
        emp_id,
        current_user.id,
        client_id=data.client_id,
        client_secret=data.client_secret,
        app_token=data.app_token,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee or Slack slot not found")
    return result
