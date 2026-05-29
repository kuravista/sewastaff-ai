from datetime import datetime, timezone
from typing import Any

from app.schemas.normalized_event import NormalizedEvent


def normalize_waha_event(payload: dict[str, Any], session_id: str) -> NormalizedEvent | None:
    event_type = payload.get("event")
    if event_type != "message":
        return None

    msg_payload = payload.get("payload", {})
    if not msg_payload.get("isGroup"):
        return None

    from_id = msg_payload.get("from", "")
    if from_id == "system":
        return None

    raw_type = msg_payload.get("type", "unknown")
    type_map = {
        "chat": "text",
        "image": "image",
        "document": "document",
        "audio": "audio",
        "ptt": "audio",
        "video": "video",
        "sticker": "sticker",
    }
    msg_type = type_map.get(raw_type, "unknown")

    data = msg_payload.get("_data", {})

    # Timestamp conversion (assuming it's a Unix timestamp if present)
    timestamp_val = msg_payload.get("timestamp")
    if isinstance(timestamp_val, (int, float)):
        ts = datetime.fromtimestamp(timestamp_val, tz=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    return NormalizedEvent(
        event_id=msg_payload.get("id", ""),
        session_id=session_id,
        group_id=msg_payload.get("chatId", ""),
        sender_id=from_id,
        message_type=msg_type,
        message_text=msg_payload.get("body"),
        media_url=data.get("mediaUrl"),
        media_mime=data.get("mimetype"),
        timestamp=ts,
        is_from_me=msg_payload.get("fromMe", False),
    )
