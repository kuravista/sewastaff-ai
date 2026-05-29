import base64

import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.normalized_event import NormalizedEvent

logger = get_logger(__name__)

CANNED_REPLIES = {
    "document": "Maaf, saya belum bisa baca file. Kirim via link Google Drive ya 🙏",
    "audio": "Maaf, saya belum bisa dengar voice note. Ketik saja ya 🙏",
    "video": "Maaf, video belum didukung. Ketik atau kirim gambar saja 🙏",
}


async def handle_media(
    event: NormalizedEvent,
) -> tuple[str | None, str | None]:
    if event.message_type == "image" and event.media_url:
        # Rewrite localhost WAHA URLs to Docker network hostname
        media_url = event.media_url
        media_url = media_url.replace("localhost:3000", "app-waha-1:3000")
        media_url = media_url.replace("http://localhost", "http://app-waha-1")
        
        # Add API key for auth (use header, not query param — WAHA rejects ?x-api-key)
        headers = {}
        if settings.WAHA_API_KEY:
            headers["X-Api-Key"] = settings.WAHA_API_KEY
        
        logger.info("media_download_start", media_url=media_url)
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(media_url, headers=headers)
            r.raise_for_status()
            data = r.content
        logger.info("media_download_done", bytes=len(data))
        return (base64.b64encode(data).decode(), None)

    canned = CANNED_REPLIES.get(event.message_type)
    if event.message_type in ("sticker", "unknown"):
        return (None, None)
    return (None, canned)
