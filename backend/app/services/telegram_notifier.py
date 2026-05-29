import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

async def _send(text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("Telegram bot token not configured")
        return
        
    chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
    if not chat_id:
        logger.warning("Telegram admin chat ID not configured")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.error(f"Failed to send telegram message: {str(e)}")

async def alert_session_down(session_id: str):
    await _send(f"WAHA Session DOWN: {session_id}. Scan ulang QR di panel WAHA.")

async def alert_send_dead_letter(event_id: str, group_id: str):
    await _send(f"Gagal kirim WA 3x. event={event_id} group={group_id}")

async def alert_llm_dead_letter(event_id: str, group_id: str):
    await _send(f"Gagal panggil LLM 3x. event={event_id} group={group_id}")

async def notify_rental_expiring(tenant_name: str, days_left: int):
    await _send(f"Langganan {tenant_name} berakhir dalam {days_left} hari.")
