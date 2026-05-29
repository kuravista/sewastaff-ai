from uuid import UUID, uuid4

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StaffTemplate(Base):
    __tablename__ = "staff_templates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_emoji: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_monthly_idr: Mapped[int] = mapped_column(Integer, default=99000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
