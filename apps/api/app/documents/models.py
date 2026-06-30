from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False
    )
    employee_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("employees.id"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cognee_document_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="uploaded", server_default="uploaded"
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="documents"
    )
    employee: Mapped["Employee | None"] = relationship(
        "Employee", back_populates="documents"
    )
