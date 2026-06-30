from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    personality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duties: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Bot tokens — encrypted at rest via AES-256-GCM
    discord_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    mcp_connections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    memory_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Cognee IDs — populated in Phase 4 fork
    cognee_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cognee_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cognee_dataset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cognee_dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(
        String(50), default="inactive", server_default="inactive"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), default=None, nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="employees"
    )
    channel_assignments: Mapped[list["ChannelAssignment"]] = relationship(
        "ChannelAssignment", back_populates="employee"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="employee"
    )
