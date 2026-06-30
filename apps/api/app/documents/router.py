from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.documents.schemas import DocumentResponse
from app.documents.service import delete_document, get_document, list_documents, save_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    organization_id: UUID = Form(...),
    employee_id: UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Upload a file and store its metadata. File saved to disk under upload_dir."""
    doc = await save_document(db, organization_id, current_user.id, file, employee_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return DocumentResponse.model_validate(doc, from_attributes=True)


@router.get("", response_model=list[DocumentResponse])
async def list_org_documents(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    """List all documents for an organization."""
    docs = await list_documents(db, organization_id, current_user.id)
    if docs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return [DocumentResponse.model_validate(d, from_attributes=True) for d in docs]


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document_route(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    doc = await get_document(db, doc_id, current_user.id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(doc, from_attributes=True)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_route(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await delete_document(db, doc_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
