from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GroupBinding(Base):
    __tablename__ = "group_bindings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled')",
            name="ck_group_bindings_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rental_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rental_instances.id"), unique=True, nullable=False
    )
    group_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    invite_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rental_instance: Mapped["RentalInstance"] = relationship(  # noqa: F821
        "RentalInstance", backref="group_binding", lazy="selectin"
    )
