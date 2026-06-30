import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.documents.models import Document
from app.organizations.models import Organization


async def _verify_org(db: AsyncSession, org_id: UUID, user_id: UUID) -> Organization | None:
    return await db.scalar(
        select(Organization).where(
            Organization.id == org_id, Organization.owner_id == user_id
        )
    )


def _sanitize_filename(raw: str | None) -> str:
    """Strip path separators and null bytes to prevent traversal."""
    if not raw:
        return "upload"
    # Take only the basename (strips any directory components)
    safe = raw.replace("\\", "/").split("/")[-1]
    # Remove null bytes and leading dots that could represent hidden files
    safe = safe.replace("\x00", "").lstrip(".")
    # Collapse to alphanumeric + safe punctuation, max 255 chars
    safe = re.sub(r"[^\w.\-]", "_", safe)[:255]
    return safe or "upload"


async def save_document(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    file: UploadFile,
    employee_id: UUID | None = None,
) -> Document | None:
    """Save uploaded file metadata (and file to disk). Returns None if org not found."""
    org = await _verify_org(db, org_id, user_id)
    if org is None:
        return None

    content = await file.read()
    size = len(content)

    safe_name = _sanitize_filename(file.filename)

    # Store file under upload_dir / org_id / safe_filename
    upload_root = Path(settings.upload_dir) / str(org_id)
    upload_root.mkdir(parents=True, exist_ok=True)
    dest = upload_root / safe_name
    dest.write_bytes(content)

    doc = Document(
        org_id=org_id,
        employee_id=employee_id,
        filename=safe_name,
        content_type=file.content_type,
        size_bytes=size,
        storage_path=str(dest),
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(
    db: AsyncSession, org_id: UUID, user_id: UUID
) -> list[Document] | None:
    org = await _verify_org(db, org_id, user_id)
    if org is None:
        return None
    result = await db.execute(
        select(Document)
        .where(Document.org_id == org_id)
        .order_by(Document.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def get_document(
    db: AsyncSession, doc_id: UUID, user_id: UUID
) -> Document | None:
    """Fetch a document — checks ownership via org join."""
    doc = await db.scalar(select(Document).where(Document.id == doc_id))
    if doc is None:
        return None
    org = await _verify_org(db, doc.org_id, user_id)
    if org is None:
        return None
    return doc


async def delete_document(
    db: AsyncSession, doc_id: UUID, user_id: UUID
) -> bool:
    doc = await get_document(db, doc_id, user_id)
    if doc is None:
        return False
    # Remove from disk (best-effort)
    if doc.storage_path and os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
    await db.delete(doc)
    await db.commit()
    return True
