from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.employees.models import Employee
from app.memory.schemas import (
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryResultSchema,
    MemorySearchRequest,
    MemorySearchResponse,
)
from app.memory.service import memory_ingest, memory_search
from app.organizations.models import Organization

router = APIRouter(prefix="/api/memory", tags=["memory"])


async def _verify_employee_ownership(
    db: AsyncSession, employee_id: UUID, user_id: UUID
) -> None:
    """Raise 404 if employee does not belong to an org owned by user_id."""
    emp = await db.scalar(
        select(Employee)
        .join(Organization, Employee.org_id == Organization.id)
        .where(Employee.id == employee_id, Organization.owner_id == user_id)
    )
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )


@router.post("/search", response_model=MemorySearchResponse)
async def search(
    data: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemorySearchResponse:
    """Search organization/employee memory database."""
    await _verify_employee_ownership(db, data.employee_id, current_user.id)
    results = await memory_search(data.query, data.employee_id)
    schemas = [
        MemoryResultSchema(
            text=r.text,
            dataset_name=r.dataset_name,
            source=r.source,
            score=r.score,
        )
        for r in results
    ]
    return MemorySearchResponse(results=schemas, query=data.query)


@router.post("/ingest", response_model=MemoryIngestResponse)
async def ingest(
    data: MemoryIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryIngestResponse:
    """Ingest fact or document snippet into employee memory database."""
    await _verify_employee_ownership(db, data.employee_id, current_user.id)
    success = await memory_ingest(data.content, data.employee_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest memory content",
        )
    return MemoryIngestResponse(status="success")
