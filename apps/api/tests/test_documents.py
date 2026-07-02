"""Baseline tests for document service — pins current behavior before Phase 1 changes.

These tests verify the CURRENT state of save_document, delete_document, etc.
so we can confirm existing paths don't break when we add employee routing,
all-format Cognee ingest, and status progression in Phase 1.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure all model modules are imported before SQLAlchemy mapper configuration
import app.auth.models  # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.employees.models  # noqa: F401
import app.organizations.models  # noqa: F401
import app.agent.tools.mcp.models  # noqa: F401
import app.gateway.models  # noqa: F401


def _make_org(org_id: UUID | None = None, **overrides) -> MagicMock:
    org = MagicMock()
    org.id = org_id or uuid4()
    org.name = "Test Org"
    org.description = "Test description"
    org.what_it_does = "Tests stuff"
    org.cognee_tenant_id = "tenant-123"
    org.cognee_tenant_name = "Test Org"
    org.cognee_system_user_id = "sys-user-456"
    org.cognee_system_user_name = "system+tenant-123@openhuman.internal"
    org.cognee_dataset_id = "ds-789"
    org.cognee_dataset_name = "company-tenant-123"
    for k, v in overrides.items():
        setattr(org, k, v)
    return org


def _make_emp(emp_id: UUID | None = None, **overrides) -> MagicMock:
    emp = MagicMock()
    emp.id = emp_id or uuid4()
    emp.name = "Test Employee"
    emp.org_id = uuid4()
    emp.cognee_user_id = "ai-user-111"
    emp.cognee_user_name = "ai-test+tenant@openhuman.internal"
    emp.cognee_dataset_id = "ds-222"
    emp.cognee_dataset_name = f"employee-{emp.id}"
    for k, v in overrides.items():
        setattr(emp, k, v)
    return emp


class TestSaveDocumentCurrentBehavior:
    """Pin current save_document behavior — org-only Cognee, text-only ingest, status="uploaded"."""

    @pytest.mark.anyio
    async def test_save_without_employee_id_ingests_to_org_dataset(self):
        """Current: documents without employee_id go to org Cognee dataset."""
        from app.documents.service import save_document
        from app.documents.models import Document

        org = _make_org()
        file = MagicMock()
        file.filename = "test.txt"
        file.content_type = "text/plain"
        file.read = AsyncMock(return_value=b"Hello world")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/test.txt")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember") as mock_remember:
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert result.status == "uploaded"
        # Verify Cognee was called with ORG dataset
        assert mock_remember.called
        _, dataset_name, user_id = mock_remember.call_args[0][:3]
        assert dataset_name == org.cognee_dataset_name
        assert user_id == org.cognee_system_user_id

    @pytest.mark.anyio
    async def test_save_with_employee_id_still_ingests_to_org_dataset(self):
        """Current bug (Gap 1): employee_id is stored on the doc row but
        Cognee ingest still goes to the ORG dataset, not the employee's."""
        from app.documents.service import save_document

        org = _make_org()
        emp = _make_emp()
        # Employee is in a different org — but the _verify_org check
        # only checks the org, so employee can be from anywhere
        emp.org_id = org.id

        file = MagicMock()
        file.filename = "emp_doc.txt"
        file.content_type = "text/plain"
        file.read = AsyncMock(return_value=b"Employee-specific content")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/emp_doc.txt")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember") as mock_remember:
                result = await save_document(mock_db, org.id, uuid4(), file, employee_id=emp.id)

        assert result is not None
        assert result.employee_id == emp.id
        # Gap 1: Cognee still goes to org dataset (current behavior, to be fixed in Phase 1a)
        assert mock_remember.called
        _, dataset_name, user_id = mock_remember.call_args[0][:3]
        assert dataset_name == org.cognee_dataset_name  # should be emp.cognee_dataset_name after fix

    @pytest.mark.anyio
    async def test_text_file_is_cognee_ingested(self):
        """Current: text files (txt, md, csv, json, xml) are decoded and remembered."""
        from app.documents.service import save_document

        org = _make_org()
        file = MagicMock()
        file.filename = "notes.md"
        file.content_type = "text/markdown"
        file.read = AsyncMock(return_value=b"# Markdown content")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/notes.md")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember") as mock_remember:
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert mock_remember.called
        # Verify text content was passed (current text-decode approach)
        data_arg = mock_remember.call_args[0][0] if mock_remember.call_args[0] else mock_remember.call_args.kwargs.get("data")
        assert "Markdown content" in str(data_arg)

    @pytest.mark.anyio
    async def test_binary_file_is_stored_but_not_cognee_ingested(self):
        """Current Gap 3: PDFs and binary files are stored in bucket but NOT Cognee-ingested."""
        from app.documents.service import save_document

        org = _make_org()
        file = MagicMock()
        file.filename = "report.pdf"
        file.content_type = "application/pdf"
        file.read = AsyncMock(return_value=b"%PDF-1.4 fake pdf content")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/report.pdf")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember") as mock_remember:
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert result.status == "uploaded"
        # Gap 3: PDF not Cognee-ingested (current behavior, to be fixed in Phase 1b)
        assert not mock_remember.called

    @pytest.mark.anyio
    async def test_document_status_stays_uploaded(self):
        """Current Gap 11: status is set to 'uploaded' and never progresses."""
        from app.documents.service import save_document

        org = _make_org()
        file = MagicMock()
        file.filename = "doc.txt"
        file.content_type = "text/plain"
        file.read = AsyncMock(return_value=b"content")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/doc.txt")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember"):
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert result.status == "uploaded"  # Never progresses to "indexed" (Gap 11)

    @pytest.mark.anyio
    async def test_org_not_found_returns_none(self):
        """When org doesn't belong to user, returns None."""
        from app.documents.service import save_document

        file = MagicMock()
        file.filename = "doc.txt"

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=None)  # org not found

        result = await save_document(mock_db, uuid4(), uuid4(), file)
        assert result is None

    @pytest.mark.anyio
    async def test_cognee_ingest_failure_does_not_crash(self):
        """When Cognee ingest fails, document is still saved successfully."""
        from app.documents.service import save_document

        org = _make_org()
        file = MagicMock()
        file.filename = "doc.txt"
        file.content_type = "text/plain"
        file.read = AsyncMock(return_value=b"content")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/doc.txt")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember", side_effect=RuntimeError("Cognee down")):
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert result.status == "uploaded"  # Still saved despite Cognee failure

    @pytest.mark.anyio
    async def test_cognee_skipped_when_org_not_provisioned(self):
        """Current: when org has no Cognee dataset, ingest is silently skipped (Gap 10)."""
        from app.documents.service import save_document

        org = _make_org(
            cognee_dataset_name=None,
            cognee_system_user_id=None,
        )
        file = MagicMock()
        file.filename = "doc.txt"
        file.content_type = "text/plain"
        file.read = AsyncMock(return_value=b"content")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/doc.txt")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember") as mock_remember:
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert not mock_remember.called  # Silently skipped (Gap 10 — will add warning in Phase 1b)

    @pytest.mark.anyio
    async def test_over_size_limit_skipped(self):
        """Files over 500KB skip Cognee ingest."""
        from app.documents.service import save_document

        org = _make_org()
        file = MagicMock()
        file.filename = "large.txt"
        file.content_type = "text/plain"
        file.read = AsyncMock(return_value=b"x" * 500_001)  # just over 500KB

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=org)

        with patch("app.documents.service.get_storage_backend") as mock_backend_factory:
            mock_backend = MagicMock()
            mock_backend.save = AsyncMock(return_value="org-123/large.txt")
            mock_backend_factory.return_value = mock_backend

            with patch("app.documents.service.remember") as mock_remember:
                result = await save_document(mock_db, org.id, uuid4(), file)

        assert result is not None
        assert not mock_remember.called  # Skipped due to size


class TestDeleteDocumentCurrentBehavior:
    """Pin current delete_document behavior — storage + DB cleanup, no Cognee forget."""

    @pytest.mark.anyio
    async def test_delete_removes_from_storage_and_db(self):
        from app.documents.service import delete_document

        org = _make_org()
        doc_mock = MagicMock()
        doc_mock.id = uuid4()
        doc_mock.org_id = org.id
        doc_mock.storage_path = "org-123/test.txt"
        doc_mock.storage_backend = "local"

        mock_db = AsyncMock(spec=AsyncSession)
        # get_document calls scalar twice:
        #   1) SELECT Document WHERE id = doc_id → doc_mock
        #   2) _verify_org → SELECT Organization → org
        mock_db.scalar = AsyncMock(side_effect=[doc_mock, org])

        with patch("app.documents.service.get_local_backend") as mock_local:
            mock_backend = MagicMock()
            mock_backend.delete = AsyncMock()
            mock_local.return_value = mock_backend

            result = await delete_document(mock_db, doc_mock.id, uuid4())

        assert result is True
        mock_backend.delete.assert_awaited_once_with("org-123/test.txt")
        mock_db.delete.assert_called_once_with(doc_mock)
        mock_db.commit.assert_called()

    @pytest.mark.anyio
    async def test_delete_doc_not_found_returns_false(self):
        from app.documents.service import delete_document

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.scalar = AsyncMock(return_value=None)

        result = await delete_document(mock_db, uuid4(), uuid4())
        assert result is False
