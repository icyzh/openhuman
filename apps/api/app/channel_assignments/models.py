from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChannelAssignment(Base):
    __tablename__ = "channel_assignments"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("employees.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee", back_populates="channel_assignments"
    )
