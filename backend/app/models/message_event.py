from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MessageEvent(Base):
    __tablename__ = "message_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    group_id: Mapped[str] = mapped_column(Text, nullable=False)
    sender_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_from_me: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
