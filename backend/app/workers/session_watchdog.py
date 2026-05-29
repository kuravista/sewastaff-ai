from typing import Any
import structlog

from app.core.config import settings
from app.services.waha_client import waha_client
from app.services import telegram_notifier

logger = structlog.get_logger(__name__)

async def check_sessions(ctx: dict[str, Any]):
    for session_id in settings.session_ids_list:
        status = await waha_client.get_session_status(session_id)
        logger.info("watchdog_check", session_id=session_id, status=status)
        
        if status.get("engine_state") not in ("WORKING", "CONNECTED"):
            logger.error("session_disconnected", session_id=session_id, status=status)
            await telegram_notifier.alert_session_down(session_id)
