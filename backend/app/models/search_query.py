from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID | None] = mapped_column(nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # vector(1536) via raw SQL
    user_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_template_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
