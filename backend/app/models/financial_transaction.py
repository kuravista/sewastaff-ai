from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"
    __table_args__ = (
        CheckConstraint(
            "tx_type IN ('income', 'expense', 'transfer', 'adjustment')",
            name="ck_financial_transactions_type",
        ),
        CheckConstraint(
            "status IN ('confirmed', 'pending', 'rejected')",
            name="ck_financial_transactions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rental_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rental_instances.id"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(Text, nullable=False)
    sender_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    tx_type: Mapped[str] = mapped_column(Text, nullable=False)
    amount_idr: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(Text, default="IDR", nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="confirmed", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
