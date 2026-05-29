from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import Base

class StaffIdentityMemory(Base):
    __tablename__ = "staff_identity_memories"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    rental_id = Column(PGUUID(as_uuid=True), ForeignKey("rental_instances.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=False, default="preference")
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)
    importance = Column(Float, nullable=False, default=0.5)
    source = Column(String, nullable=False, default="extracted")
    confirmed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
