from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SearchCluster(Base):
    __tablename__ = "search_clusters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    representative_query: Mapped[str] = mapped_column(Text, nullable=False)
    centroid_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # vector(1536) via raw SQL
    query_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unique_users: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="collecting", nullable=False)
    suggested_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_specialty: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_template_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
