import asyncio
import random
from typing import Any

from sqlalchemy.future import select
from pydantic import ValidationError

from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.core.logging import get_logger
from app.schemas.normalized_event import NormalizedEvent
from app.models.rental_instance import RentalInstance
from app.models.staff_template import StaffTemplate
from app.models.message_event import MessageEvent
from app.services.media_handler import handle_media
from app.services.context_builder import build_context
from app.services.llm_client import call_llm
from app.services.waha_client import waha_client
from app.services.role_compiler import compile_prompt

logger = get_logger(__name__)

CANNED_REPLIES = {
    "document": "📄 Maaf, saya belum bisa membaca dokumen. Silakan ketik pertanyaan Anda langsung ya!",
    "audio": "🎵 Maaf, saya belum bisa memproses audio/video. Silakan ketik pesan Anda ya!",
    "video": "🎵 Maaf, saya belum bisa memproses audio/video. Silakan ketik pesan Anda ya!",
}

async def persist_event(db, event: NormalizedEvent, content: str = None) -> MessageEvent:
    msg_event = MessageEvent(
        event_id=event.event_id,
        group_id=event.group_id,
        sender_id=event.sender_id,
        message_type=event.message_type,
        content=content or event.message_text,
        is_from_me=event.is_from_me,
        timestamp=event.timestamp,
        correlation_id=event.correlation_id,
    )
    db.add(msg_event)
    await db.commit()
    return msg_event

async def handle_message(ctx: dict[str, Any], event_data: dict, rental_id: str, canned_reply: bool = False):
    try:
        event = NormalizedEvent.model_validate(event_data)
    except ValidationError as e:
        logger.error("worker_parse_error", error=str(e))
        return

    logger.info("worker_dequeue", **event.log_fields())
    
    # 2. Pacing
    delay = random.uniform(3, 8)
    await asyncio.sleep(delay)
    logger.info("pacing_delay", delay=delay, **event.log_fields())

    # 3. Canned reply
    if canned_reply:
        reply_text = CANNED_REPLIES.get(event.message_type, "")
        if reply_text:
            await waha_client.send_text(event.session_id, event.group_id, reply_text)
        return

    # 4. Lock
    redis = await get_redis()
    lock_key = f"session_lock:{event.session_id}"
    was_set = await redis.set(lock_key, "1", ex=30, nx=True)
    if not was_set:
        logger.info("session_busy", **event.log_fields())
        # arq way to retry: raise exception or enqueue again. We'll rely on the caller/retry policy or re-enqueue manually
        # Simple backoff simulation: sleep and try once more or raise Exception to trigger arq retry
        raise Exception("session_busy_retry")

    try:
        # 5. DB
        async with SessionLocal() as db:
            # 6. Load DB entities
            result = await db.execute(select(RentalInstance).where(RentalInstance.id == rental_id))
            rental = result.scalars().first()
            if not rental:
                logger.error("worker_rental_not_found", rental_id=rental_id)
                return
                
            # 8. Media
            b64_image, canned_text = await handle_media(event)
            if canned_text:
                await persist_event(db, event)
                await waha_client.send_text(event.session_id, event.group_id, canned_text)
                
                out_event = event.model_copy()
                out_event.event_id = f"out_{event.event_id}"
                out_event.is_from_me = True
                out_event.message_type = "text"
                await persist_event(db, out_event, content=canned_text)
                return
                
            if b64_image:
                event._b64_image_data = b64_image
                
            try:
                # 9. Build context
                # Context builder loads history inside.
                messages = await build_context(rental, event, db)
                
                # 10. Call LLM
                reply_text = await call_llm(messages, has_image=bool(b64_image))
                
            except Exception as e:
                logger.error("worker_llm_failure", error=str(e))
                reply_text = "Maaf, sistem sedang sibuk. Mohon ulangi beberapa saat lagi."

            # 12. Send WAHA
            await waha_client.send_text(event.session_id, event.group_id, reply_text)

            # 13, 14. Persist
            await persist_event(db, event)
            
            out_event = event.model_copy()
            out_event.event_id = f"out_{event.event_id}"
            out_event.is_from_me = True
            out_event.message_type = "text"
            await persist_event(db, out_event, content=reply_text)

            # 15. Extract memory (background, non-blocking)
            _user_text = event.message_text or ""
            _rental_id = rental.id
            try:
                async def _bg_extract():
                    from app.services.memory_extractor import extract_and_save_memory
                    async with SessionLocal() as bg_db:
                        await extract_and_save_memory(_rental_id, _user_text, reply_text, bg_db)
                asyncio.create_task(_bg_extract())
            except Exception:
                pass

    finally:
        # 11. Release lock
        await redis.delete(lock_key)
