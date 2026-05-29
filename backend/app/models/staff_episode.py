from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import Base

class StaffEpisode(Base):
    __tablename__ = "staff_episodes"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    rental_id = Column(PGUUID(as_uuid=True), ForeignKey("rental_instances.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False, default="interaction")
    actor_id = Column(String)
    summary = Column(String, nullable=False)
    outcome = Column(String)
    sentiment = Column(String)
    importance = Column(Float, nullable=False, default=0.5)
    business_impact = Column(Float)
    embedding = Column(String)  # Store as String initially, will migrate to proper vector later
    source_event_id = Column(String)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
