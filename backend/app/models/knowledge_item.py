from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        CheckConstraint("type IN ('image', 'link', 'text')", name="ck_knowledge_item_type"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_knowledge_item_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rental_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("rental_instances.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
