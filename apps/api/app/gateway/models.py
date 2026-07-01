from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.employees.models import Employee


class SlackAppSlot(Base):
    """Pre-provisioned Slack app identity slot for one AI employee.

    Each slot holds a distinct Slack app's credentials (client_id, client_secret
    for OAuth, and xapp- app-level token for Socket Mode).  Slots are assigned
    1:1 to employees at creation time from an available pool.
    """

    __tablename__ = "slack_app_slots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'assigned', 'disabled')",
            name="ck_slack_app_slots_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    slack_app_id: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    app_token_enc: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(50), default="available", server_default="available"
    )

    employee_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    employee: Mapped[Employee | None] = relationship(
        "Employee",
        primaryjoin="SlackAppSlot.employee_id == Employee.id",
        uselist=False,
        viewonly=True,
    )
