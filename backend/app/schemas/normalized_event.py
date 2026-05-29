from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NormalizedEvent(BaseModel):
    event_id: str
    correlation_id: UUID = Field(default_factory=uuid4)
    session_id: str
    group_id: str
    sender_id: str
    message_type: Literal["text", "image", "document", "audio", "video", "sticker", "unknown"]
    message_text: Optional[str] = None
    media_url: Optional[str] = None
    media_mime: Optional[str] = None
    timestamp: datetime
    is_from_me: bool = False

    def log_fields(self) -> dict:
        return {
            "event_id": self.event_id,
            "correlation_id": str(self.correlation_id),
            "session_id": self.session_id,
            "group_id": self.group_id,
            "message_type": self.message_type,
        }
