from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RentalInstance(Base):
    __tablename__ = "rental_instances"
    __table_args__ = (
        CheckConstraint("status IN ('trial', 'active', 'expired', 'suspended')", name="ck_rental_instances_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff_templates.id"), nullable=False)
    custom_traits: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="trial", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
