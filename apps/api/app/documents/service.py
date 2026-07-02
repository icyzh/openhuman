from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.documents.models import Document
from app.documents.schemas import DocumentsStatsResponse
from app.documents.utils import sanitize_filename
from app.employees.models import Employee
from app.memory.service import remember
from app.organizations.models import Organization
from app.storage import get_local_backend, get_s3_backend, get_storage_backend
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)


async def _verify_org(db: AsyncSession, org_id: UUID, user_id: UUID) -> Organization | None:
    return await db.scalar(
        select(Organization).where(
            Organization.id == org_id, Organization.owner_id == user_id
        )
    )


def _backend_for(doc: Document) -> StorageBackend:
    """Return the backend that holds this document's file bytes."""
    return get_local_backend() if doc.storage_backend == "local" else get_s3_backend()


async def save_document(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    file: UploadFile,
    employee_id: UUID | None = None,
) -> Document | None:
    """Save uploaded file via the configured storage backend. Returns None if org not found."""
    org = await _verify_org(db, org_id, user_id)
    if org is None:
        return None

    content = await file.read()
    size = len(content)

    backend = get_storage_backend()
    storage_path = await backend.save(
        org_id=org_id,
        filename=file.filename or "upload",
        content=content,
        content_type=file.content_type,
    )

    doc = Document(
        org_id=org_id,
        employee_id=employee_id,
        filename=sanitize_filename(file.filename),
        content_type=file.content_type,
        size_bytes=size,
        storage_path=storage_path,
        storage_backend=settings.storage_backend,
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # ── Cognee ingest — all file formats, path-based (best-effort, non-blocking) ─
    _COGNEE_MAX_SIZE = 500_000  # bytes

    # Determine target dataset: employee docs go to employee dataset (Phase 1a)
    if employee_id:
        emp = await db.get(Employee, employee_id)
        if emp and emp.cognee_dataset_name and emp.cognee_user_id and emp.cognee_dataset_id:
            target_dataset = emp.cognee_dataset_name
            target_user_id = emp.cognee_user_id
            target_dataset_id = emp.cognee_dataset_id
            target_label = f"employee-{employee_id}"
        else:
            missing_parts = []
            if not emp:
                missing_parts.append("employee not found")
            else:
                if not emp.cognee_user_id:
                    missing_parts.append("cognee_user_id")
                if not emp.cognee_dataset_name:
                    missing_parts.append("cognee_dataset_name")
                if not emp.cognee_dataset_id:
                    missing_parts.append("cognee_dataset_id")
            logger.warning(
                "Employee %s has incomplete Cognee provisioning (%s), "
                "falling back to org dataset for doc %s",
                employee_id, ", ".join(missing_parts) if missing_parts else "unknown", doc.filename,
            )
            target_dataset = org.cognee_dataset_name
            target_user_id = org.cognee_system_user_id
            target_dataset_id = org.cognee_dataset_id
            target_label = f"org-{org.id} (fallback from employee)"
    else:
        target_dataset = org.cognee_dataset_name
        target_user_id = org.cognee_system_user_id
        target_dataset_id = org.cognee_dataset_id
        target_label = f"org-{org.id}"

    if not target_dataset or not target_user_id:
        logger.warning(
            "Cognee ingest skipped for doc %s — Cognee not provisioned for %s",
            doc.filename, target_label,
        )
    elif size > _COGNEE_MAX_SIZE:
        logger.debug(
            "Cognee ingest skipped for %s (%d bytes exceeds %d limit)",
            doc.filename, size, _COGNEE_MAX_SIZE,
        )
    else:
        try:
            suffix = Path(doc.filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                await remember(
                    tmp_path,
                    target_dataset,
                    target_user_id,
                    dataset_id=target_dataset_id,
                    background=True,
                )
                doc.status = "indexed"
            except Exception:
                doc.status = "failed"
                raise
            finally:
                os.unlink(tmp_path)
        except Exception:
            logger.exception(
                "Cognee ingest failed for doc %s (%s, %d bytes, target=%s)",
                doc.id, doc.filename, size, target_label,
            )
            doc.status = "failed"

        # Persist status update from Cognee attempt
        await db.commit()
    # ── End Cognee ──────────────────────────────────────────────────────────────

    return doc


async def list_documents(
    db: AsyncSession, org_id: UUID, user_id: UUID, employee_id: UUID | None = None
) -> list[Document] | None:
    org = await _verify_org(db, org_id, user_id)
    if org is None:
        return None
    stmt = (
        select(Document)
        .options(joinedload(Document.employee))
        .where(Document.org_id == org_id)
    )
    if employee_id is not None:
        stmt = stmt.where(Document.employee_id == employee_id)
    stmt = stmt.order_by(Document.uploaded_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_documents_stats(
    db: AsyncSession, org_id: UUID, user_id: UUID
) -> DocumentsStatsResponse | None:
    """Return aggregate document statistics for an organization."""
    org = await _verify_org(db, org_id, user_id)
    if org is None:
        return None

    result = await db.execute(
        select(
            func.count(Document.id).label("total_files"),
            func.coalesce(func.sum(Document.size_bytes), 0).label("total_size_bytes"),
            func.sum(
                case((Document.employee_id.is_(None), 1), else_=0)
            ).label("org_files_count"),
            func.coalesce(
                func.sum(
                    case((Document.employee_id.is_(None), Document.size_bytes), else_=0)
                ),
                0,
            ).label("org_size_bytes"),
            func.sum(
                case((Document.employee_id.isnot(None), 1), else_=0)
            ).label("agent_files_count"),
            func.coalesce(
                func.sum(
                    case((Document.employee_id.isnot(None), Document.size_bytes), else_=0)
                ),
                0,
            ).label("agent_size_bytes"),
            func.count(func.distinct(Document.employee_id)).label(
                "agents_with_files_count"
            ),
        ).where(Document.org_id == org_id)
    )
    row = result.one()
    return DocumentsStatsResponse(
        total_files=row.total_files,
        total_size_bytes=row.total_size_bytes,
        org_files_count=row.org_files_count,
        org_size_bytes=row.org_size_bytes,
        agent_files_count=row.agent_files_count,
        agent_size_bytes=row.agent_size_bytes,
        agents_with_files_count=row.agents_with_files_count,
    )


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
    """Delete a document from storage and database.

    Note: Cognee knowledge is NOT deleted. Cognee's forget() operates at the
    dataset level, not per-document. Stale knowledge may persist in the graph
    until the containing dataset is forgotten (org/employee deletion).
    This is an accepted limitation for v1.
    """
    doc = await get_document(db, doc_id, user_id)
    if doc is None:
        return False
    # Remove from the backend that stored it
    if doc.storage_path:
        backend = _backend_for(doc)
        await backend.delete(doc.storage_path)
    await db.delete(doc)
    await db.commit()
    return True


async def get_document_stream(
    db: AsyncSession, doc_id: UUID, user_id: UUID
) -> tuple[AsyncGenerator[bytes, None], Document | None]:
    """Get a streaming reader for document content.

    Returns (stream_generator, document) or (empty_generator, None) if not found.
    """
    doc = await get_document(db, doc_id, user_id)
    if doc is None or doc.storage_path is None:
        async def _empty() -> AsyncGenerator[bytes, None]:
            return
            yield  # pragma: no cover — makes this an async generator
        return _empty(), None

    backend = _backend_for(doc)
    return backend.read_stream(doc.storage_path), doc
