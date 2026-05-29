from __future__ import annotations

import asyncio
import calendar
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.models.group_binding import GroupBinding
from app.models.message_event import MessageEvent
from app.models.rental_instance import RentalInstance
from app.models.reminder import Reminder
from app.models.staff_template import StaffTemplate
from app.schemas.normalized_event import NormalizedEvent
from app.services.context_builder import build_context
from app.services.llm_client import call_llm
from app.services.media_handler import handle_media
from app.services.memory_extractor import extract_and_save_memory
from app.services.finance_extractor import extract_finance_query, extract_finance_transaction
from app.services.finance_service import answer_finance_query, save_finance_transaction
from app.services.reminder_extractor import extract_reminder
from app.services.role_compiler import compile_prompt
from app.services.waha_client import waha_client, WAHAClient

logger = get_logger(__name__)

SUPPORTED_TYPES = {"chat", "text", "image"}
TYPE_MAP = {
    "chat": "text",
    "text": "text",
    "image": "image",
}


def _clean_reminder_title(title: str) -> str:
    title = (title or "reminder").strip()
    for prefix in ("Reminder ", "Pengingat ", "Ingat "):
        if title.lower().startswith(prefix.lower()):
            title = title[len(prefix):].strip()
            break
    return title[:1].lower() + title[1:] if title else "reminder"


def _build_reminder_message(title: str, description: str | None = None) -> str:
    topic = _clean_reminder_title(title)
    templates = [
        "Hey, waktunya {topic} ya. Jangan ditunda dulu 😄",
        "Reminder kecil nih: {topic}. Yuk gas sekarang ⏰",
        "Udah waktunya {topic}. Aku ingetin sesuai janji ya 🙌",
        "Ping! Jangan lupa {topic} ya ✨",
        "Ini pengingatnya: {topic}. Semangat, beresin sekarang ya 💪",
    ]
    text = templates[sum(ord(c) for c in topic) % len(templates)].format(topic=topic)
    if description:
        text += f"\n\nCatatan: {description}"
    return text


def _serialized(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("_serialized") or value.get("id") or "")
    return str(value or "")


logger_jakarta = ZoneInfo("Asia/Jakarta")

# ── FINANCE QUERY DETECTION ───────────────────────────────────────────────────
_FINANCE_QUERY_PATTERN = re.compile(
    r"(?i)\b(pengeluaran|pemasukan|penghasilan|omzet|profit|rekap|laporan|sisa|saldo)\b.*\b(hari ini|minggu ini|bulan ini|bulan lalu|terbesar|total|list|brp|berapa|saja)\b"
    r"|\b(rekap|laporan|saldo|sisa)\s*(keuangan|transaksi|brp|berapa|saya|bulan)\b"
    r"|\b(sisa saldo|saldo (?:saya|brp|berapa))\b"
)

# ── FINANCE TRANSACTION DETECTION ────────────────────────────────────────────
_FINANCE_TX_VERBS = re.compile(
    r"(?i)\b(beli|belanja|bayar(?:an)?|biaya|ongkos|jajan|makan|minum|service|servis|ganti|isi|topup|langganan|transfer|kirim|terima|masuk|keluar|catat|tulis|simpen|penghasilan|pemasukan|pengeluaran|pengluaran|dapat|dapet|habis)\b"
)
_FINANCE_MONEY = re.compile(
    r"(?i)\b\d+\s*(?:rb|ribu|jt|juta?|jit[ae]?|k|m|ratus(?:an)?|rupiah)\b"
    r"|\bRp\s?\d"
)
_IMAGE_FINANCE_KEYWORDS = re.compile(
    r"(?i)\b(struk|nota|bukti|bayar|beli|transfer|receipt|invoice)\b"
)


def _is_finance_query(text: str) -> bool:
    return bool(_FINANCE_QUERY_PATTERN.search(text))


def _is_finance_transaction(text: str, has_media: bool) -> bool:
    if has_media and _IMAGE_FINANCE_KEYWORDS.search(text):
        return True
    return bool(_FINANCE_TX_VERBS.search(text) and _FINANCE_MONEY.search(text))

_LIST_PATTERNS = re.compile(
    r"\b(list|daftar|show|lihat)\s+remind|"
    r"\breminder\s+(apa\s+saja|saya|list)|"
    r"\bpengingat\s+saya\b",
    re.IGNORECASE,
)

_CANCEL_PREFIX = re.compile(
    r"\b(hapus|cancel|batal(?:kan)?|delete)\s+remind(?:er)?\b",
    re.IGNORECASE,
)


async def _check_reminder_command(
    event: NormalizedEvent, rental_id, db_session
) -> bool:
    """Detect & handle reminder list/cancel commands deterministically.

    Returns True if the message was handled (skip LLM), False otherwise.
    """
    text = (event.message_text or "").strip()
    if not text:
        return False

    # ── LIST ──────────────────────────────────────────────────────
    if _LIST_PATTERNS.search(text):
        return await _handle_list_reminders(event, rental_id, db_session)

    # ── CANCEL ────────────────────────────────────────────────────
    cancel_match = _CANCEL_PREFIX.search(text)
    if cancel_match:
        keyword = text[cancel_match.end():].strip().strip('"\'')
        return await _handle_cancel_reminder(event, rental_id, db_session, keyword)

    return False


async def _handle_list_reminders(
    event: NormalizedEvent, rental_id, db_session
) -> bool:
    result = await db_session.execute(
        select(Reminder)
        .where(
            Reminder.rental_id == rental_id,
            Reminder.group_id == event.group_id,
            Reminder.status.in_(["pending", "sent"]),
        )
        .order_by(Reminder.fire_at.asc())
    )
    reminders = result.scalars().all()

    if not reminders:
        await waha_client.send_text(
            event.session_id, event.group_id,
            "Belum ada reminder aktif nih. Mau bikin satu? 😊"
        )
        return True

    lines = ["📋 *Daftar Reminder:*\n"]
    for i, r in enumerate(reminders, 1):
        fire_local = r.fire_at.astimezone(logger_jakarta)
        time_str = fire_local.strftime("%d %b %Y %H:%M WIB")
        status_badge = "⏳" if r.status == "pending" else "✅"
        recur_badge = ""
        if r.recurrence:
            recur_badge = f" [🔁 {r.recurrence}]"
        media_badge = " 📸" if r.media_url else ""
        lines.append(
            f"{i}. {status_badge} *{r.title}* — {time_str}{recur_badge}{media_badge}"
        )

    await waha_client.send_text(event.session_id, event.group_id, "\n".join(lines))
    return True


async def _handle_cancel_reminder(
    event: NormalizedEvent, rental_id, db_session, keyword: str
) -> bool:
    if not keyword:
        await waha_client.send_text(
            event.session_id, event.group_id,
            "Mau hapus reminder yang mana? Contoh: *hapus reminder beli bahan*"
        )
        return True

    # ILIKE search on title
    result = await db_session.execute(
        select(Reminder)
        .where(
            Reminder.rental_id == rental_id,
            Reminder.group_id == event.group_id,
            Reminder.status == "pending",
            Reminder.title.ilike(f"%{keyword}%"),
        )
        .order_by(Reminder.fire_at.asc())
    )
    matches = result.scalars().all()

    if not matches:
        await waha_client.send_text(
            event.session_id, event.group_id,
            "Gak ketemu reminder dengan judul itu. Ketik *list reminder* untuk lihat semua."
        )
        return True

    # Cancel first match
    reminder = matches[0]
    reminder.status = "cancelled"
    await db_session.commit()

    await waha_client.send_text(
        event.session_id, event.group_id,
        f"✅ Reminder *{reminder.title}* udah dibatalkan ya."
    )
    logger.info(
        "reminder_cancelled_via_command",
        reminder_id=str(reminder.id),
        title=reminder.title,
        group_id=event.group_id,
    )
    return True


def _extract_group_id(payload: dict[str, Any]) -> str:
    # GoWS group messages: "from" = group JID, "to" = bot, "participant" = actual sender
    candidates = (
        payload.get("from"),
        payload.get("to"),
        payload.get("chatId"),
        payload.get("chat", {}).get("id") if isinstance(payload.get("chat"), dict) else None,
    )
    for candidate in candidates:
        value = _serialized(candidate)
        if value.endswith("@g.us"):
            return value
    return ""


def _extract_sender_id(payload: dict[str, Any], group_id: str) -> str:
    # In GoWS group messages, "participant" is the actual sender
    for key in ("participant", "author"):
        value = _serialized(payload.get(key))
        if value and value != group_id:
            return value
    # Fallback: "from" might be sender in DMs but group in group msgs
    value = _serialized(payload.get("from"))
    if value and value != group_id:
        return value
    return ""


def _extract_event_id(payload: dict[str, Any]) -> str:
    value = payload.get("id")
    if isinstance(value, dict):
        return str(value.get("_serialized") or value.get("id") or "")
    return str(value or "")


def _extract_timestamp(payload: dict[str, Any]) -> datetime:
    timestamp_val = payload.get("timestamp") or payload.get("t")
    if isinstance(timestamp_val, (int, float)):
        # WAHA can send seconds or milliseconds.
        if timestamp_val > 10_000_000_000:
            timestamp_val = timestamp_val / 1000
        return datetime.fromtimestamp(timestamp_val, tz=timezone.utc)
    return datetime.now(timezone.utc)


def normalize_gows_message(payload: dict[str, Any], session_id: str = "default") -> NormalizedEvent | None:
    # GoWS doesn't always set "type" — infer from hasMedia + body presence
    raw_type = str(payload.get("type") or "").lower()
    has_media = payload.get("hasMedia") is True
    has_body = bool(payload.get("body"))
    
    if not raw_type:
        if has_media:
            # Could check media mimetype but default to image for now
            raw_type = "image"
        elif has_body:
            raw_type = "chat"
        else:
            raw_type = "unknown"
    
    group_id = _extract_group_id(payload)

    if payload.get("fromMe") is True:
        logger.info("waha_ws_skip_from_me", group_id=group_id, raw_type=raw_type)
        return None

    if not group_id.endswith("@g.us"):
        logger.info("waha_ws_skip_non_group", group_id=group_id, raw_type=raw_type)
        return None

    if raw_type not in SUPPORTED_TYPES:
        logger.info("waha_ws_skip_unsupported_type", group_id=group_id, raw_type=raw_type, payload_keys=list(payload.keys()), payload_type=repr(payload.get("type")))
        return None

    event_id = _extract_event_id(payload)
    if not event_id:
        event_id = f"{group_id}:{payload.get('timestamp') or datetime.now(timezone.utc).timestamp()}"

    data = payload.get("_data") if isinstance(payload.get("_data"), dict) else {}
    media = payload.get("media") if isinstance(payload.get("media"), dict) else {}

    return NormalizedEvent(
        event_id=event_id,
        session_id=session_id,
        group_id=group_id,
        sender_id=_extract_sender_id(payload, group_id),
        message_type=TYPE_MAP.get(raw_type, "unknown"),
        message_text=payload.get("body") or payload.get("caption") or "",
        media_url=payload.get("mediaUrl") or data.get("mediaUrl") or media.get("url"),
        media_mime=payload.get("mimetype") or data.get("mimetype") or media.get("mimetype"),
        timestamp=_extract_timestamp(payload),
        is_from_me=bool(payload.get("fromMe", False)),
    )


async def _save_message_event(event: NormalizedEvent, ai_reply: str | None = None) -> None:
    async with SessionLocal() as db:
        try:
            db.add(
                MessageEvent(
                    event_id=event.event_id,
                    group_id=event.group_id,
                    sender_id=event.sender_id,
                    message_type=event.message_type,
                    content=event.message_text or "",
                    is_from_me=False,
                    timestamp=event.timestamp,
                    correlation_id=event.correlation_id,
                )
            )
            if ai_reply:
                db.add(
                    MessageEvent(
                        event_id=f"{event.event_id}:reply",
                        group_id=event.group_id,
                        sender_id="assistant",
                        message_type="text",
                        content=ai_reply,
                        is_from_me=True,
                        timestamp=datetime.now(timezone.utc),
                        correlation_id=event.correlation_id,
                    )
                )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.info("waha_ws_message_event_duplicate", **event.log_fields())
        except Exception as exc:
            await db.rollback()
            logger.error("waha_ws_message_event_save_failed", error=str(exc), **event.log_fields())


async def _extract_memory_background(rental_id, user_msg: str, ai_reply: str) -> None:
    async with SessionLocal() as db:
        await extract_and_save_memory(rental_id, user_msg, ai_reply, db)


async def _extract_and_save_reminder(
    rental_id,
    group_id: str,
    sender_id: str,
    user_msg: str,
    media_url: str | None = None,
    media_mime: str | None = None,
) -> None:
    """Extract reminder intent from message and save to DB if found."""
    try:
        has_media = bool(media_url and media_mime and media_mime.startswith("image/"))
        result = await extract_reminder(user_msg, has_media=has_media)
        if not result.get("has_reminder"):
            return

        async with SessionLocal() as db:
            reminder = Reminder(
                rental_id=rental_id,
                group_id=group_id,
                title=result["title"],
                description=result.get("description"),
                fire_at=result["fire_at"],
                timezone="Asia/Jakarta",
                status="pending",
                recurrence=result.get("recurrence"),
                created_by=sender_id,
                media_url=media_url if has_media else None,
                media_mime=media_mime if has_media else None,
            )
            db.add(reminder)
            await db.commit()
            logger.info(
                "reminder_saved",
                reminder_id=str(reminder.id),
                title=result["title"],
                fire_at=result["fire_at"].isoformat(),
                recurrence=result.get("recurrence"),
                group_id=group_id,
            )
    except Exception as e:
        logger.error(
            "reminder_extract_save_failed",
            error=str(e),
            group_id=group_id,
            sender_id=sender_id,
        )


async def _reminder_scheduler_loop() -> None:
    """Poll for due reminders and fire them. Runs every 30 seconds."""
    await asyncio.sleep(5)  # grace period on startup
    logger.info("reminder_scheduler_started")

    while True:
        try:
            await _fire_due_reminders()
        except Exception as e:
            logger.error("reminder_scheduler_error", error=str(e))
        await asyncio.sleep(30)


async def _fire_due_reminders() -> None:
    """Query pending reminders that are due and send them."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        result = await db.execute(
            select(Reminder).where(
                Reminder.status == "pending",
                Reminder.fire_at <= now,
            )
        )
        reminders = result.scalars().all()

        if not reminders:
            return

        logger.info("reminder_scheduler_due_count", count=len(reminders))

        for reminder in reminders:
            try:
                # Generate human-like reminder text with personality
                text = _build_reminder_message(reminder.title, reminder.description)

                # Send as image if media attached, otherwise plain text
                if reminder.media_url:
                    try:
                        image_data = await waha_client.download_media(reminder.media_url)
                        sent = await waha_client.send_image(
                            "default", reminder.group_id, image_data,
                            caption=text, mimetype=reminder.media_mime or "image/jpeg",
                        )
                    except Exception as img_err:
                        logger.warning(
                            "reminder_image_send_fallback",
                            reminder_id=str(reminder.id),
                            error=str(img_err),
                        )
                        # Fallback to text-only if image fails
                        sent = await waha_client.send_text("default", reminder.group_id, text)
                else:
                    sent = await waha_client.send_text("default", reminder.group_id, text)
                if not sent:
                    reminder.status = "error"
                    reminder.error_message = "send_text returned False"
                    logger.error(
                        "reminder_send_failed",
                        reminder_id=str(reminder.id),
                        group_id=reminder.group_id,
                    )
                    continue

                reminder.status = "sent"
                reminder.sent_at = datetime.now(timezone.utc)
                logger.info(
                    "reminder_fired",
                    reminder_id=str(reminder.id),
                    title=reminder.title,
                    group_id=reminder.group_id,
                )

                # Create next occurrence for recurring reminders
                if reminder.recurrence:
                    next_fire_at = _calc_next_fire_at(
                        reminder.fire_at, reminder.recurrence
                    )
                    next_reminder = Reminder(
                        rental_id=reminder.rental_id,
                        group_id=reminder.group_id,
                        title=reminder.title,
                        description=reminder.description,
                        fire_at=next_fire_at,
                        timezone=reminder.timezone,
                        status="pending",
                        recurrence=reminder.recurrence,
                        created_by=reminder.created_by,
                        media_url=reminder.media_url,
                        media_mime=reminder.media_mime,
                    )
                    db.add(next_reminder)
                    logger.info(
                        "reminder_next_occurrence",
                        reminder_id=str(reminder.id),
                        next_fire_at=next_fire_at.isoformat(),
                    )

                await db.commit()

            except Exception as e:
                reminder.status = "error"
                reminder.error_message = str(e)[:500]
                logger.error(
                    "reminder_fire_error",
                    reminder_id=str(reminder.id),
                    error=str(e),
                )
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()


def _calc_next_fire_at(current_fire_at: datetime, recurrence: str) -> datetime:
    """Calculate next fire_at for recurring reminder."""
    if recurrence == "daily":
        return current_fire_at + timedelta(days=1)
    elif recurrence == "weekly":
        return current_fire_at + timedelta(weeks=1)
    elif recurrence == "monthly":
        # Add one calendar month, clamping to last day of next month
        month = current_fire_at.month + 1
        year = current_fire_at.year
        if month > 12:
            month = 1
            year += 1
        max_day = calendar.monthrange(year, month)[1]
        day = min(current_fire_at.day, max_day)
        try:
            return current_fire_at.replace(year=year, month=month, day=day)
        except ValueError:
            return current_fire_at + timedelta(days=30)
    return current_fire_at


async def handle_inbound_message(payload: dict[str, Any], session_id: str = "default") -> None:
    event = normalize_gows_message(payload, session_id=session_id)
    if event is None:
        return

    logger.info("waha_ws_message_received", **event.log_fields())

    redis = await get_redis()
    dedup_key = f"dedup:{event.event_id}"
    was_set = await redis.set(dedup_key, "1", ex=3600, nx=True)
    if not was_set:
        logger.info("waha_ws_duplicate_skipped", **event.log_fields())
        return

    async with SessionLocal() as db:
        result = await db.execute(
            select(GroupBinding).where(
                GroupBinding.group_id == event.group_id,
                GroupBinding.status == "active",
            )
        )
        binding = result.scalars().first()
        if not binding:
            logger.info("waha_ws_no_active_binding", **event.log_fields())
            return

        result = await db.execute(select(RentalInstance).where(RentalInstance.id == binding.rental_id))
        rental = result.scalars().first()
        if not rental or rental.status not in ("trial", "active"):
            logger.info(
                "waha_ws_rental_inactive",
                rental_id=str(binding.rental_id),
                rental_status=getattr(rental, "status", None),
                **event.log_fields(),
            )
            return

        if event.message_text:
            handled = await _check_reminder_command(event, binding.rental_id, db)
            if handled:
                await _save_message_event(event, None)
                return

            text_for_check = event.message_text.strip().lower()
            has_media = bool(event.media_url)
            
            # ── FINANCE INTERCEPTORS ──
            if _is_finance_query(text_for_check):
                extraction = await extract_finance_query(event.message_text)
                if extraction.get("has_query"):
                    ans = await answer_finance_query(db, binding.rental_id, event.group_id, extraction)
                    sent = await waha_client.send_text(event.session_id, event.group_id, ans)
                    if sent:
                        await _save_message_event(event, ans)
                        return
                        
            if _is_finance_transaction(text_for_check, has_media):
                # Optionally use b64_image for context if already downloaded, but we can just use the caption/text
                extraction = await extract_finance_transaction(event.message_text, has_media=has_media)
                if extraction.get("has_transaction"):
                    tx = await save_finance_transaction(
                        db, binding.rental_id, event.group_id, event.sender_id, event, extraction
                    )
                    
                    rp_amt = f"Rp{tx.amount_idr:,}".replace(",", ".")
                    verb = "Pemasukan" if tx.tx_type == "income" else "Pengeluaran" if tx.tx_type == "expense" else "Transaksi"
                    ans = f"✅ {verb} *{rp_amt}* berhasil dicatat.\nKategori: {tx.category or 'Lainnya'}\nKeterangan: {tx.description}"
                    
                    if tx.tx_type in ["expense", "transfer"]:
                        # Check if balance is negative after this expense
                        from sqlalchemy import case, func
                        from app.models.financial_transaction import FinancialTransaction
                        from datetime import datetime, time, timedelta
                        from zoneinfo import ZoneInfo
                        jkt_tz = ZoneInfo("Asia/Jakarta")
                        now = datetime.now(jkt_tz)
                        start = datetime(now.year, now.month, 1, tzinfo=jkt_tz)
                        
                        res = await db.execute(select(
                            func.coalesce(func.sum(case((FinancialTransaction.tx_type == "income", FinancialTransaction.amount_idr), else_=0)), 0),
                            func.coalesce(func.sum(case((FinancialTransaction.tx_type.in_(["expense", "transfer"]), FinancialTransaction.amount_idr), else_=0)), 0),
                        ).where(
                            FinancialTransaction.rental_id == binding.rental_id,
                            FinancialTransaction.group_id == event.group_id,
                            FinancialTransaction.status == "confirmed",
                            FinancialTransaction.transaction_date >= start
                        ))
                        income, expense = res.one()
                        if (int(income or 0) - int(expense or 0)) < 0:
                            ans += "\n\n⚠️ Peringatan: Saldo bulan ini minus! Pengeluaran melebihi pemasukan."

                    if has_media:
                        ans += "\n(Gambar bukti transaksi tersimpan)"
                        
                    sent = await waha_client.send_text(event.session_id, event.group_id, ans)
                    if sent:
                        await _save_message_event(event, ans)
                        return

        result = await db.execute(select(StaffTemplate).where(StaffTemplate.id == rental.template_id))
        template = result.scalars().first()
        if not template:
            logger.error("waha_ws_template_missing", rental_id=str(rental.id), **event.log_fields())
            return

        # Compile once here for observability; build_context compiles same prompt plus memory/knowledge/history.
        compiled_prompt = compile_prompt(
            template_name=template.name,
            specialty=template.specialty or "",
            base_prompt=template.base_prompt or "",
            traits=rental.custom_traits or {},
        )
        logger.info(
            "waha_ws_prompt_compiled",
            rental_id=str(rental.id),
            template_id=str(template.id),
            prompt_chars=len(compiled_prompt),
            **event.log_fields(),
        )

        b64_image, canned_reply = await handle_media(event)
        if b64_image:
            setattr(event, "_b64_image_data", b64_image)
        if canned_reply:
            ai_reply = canned_reply
        else:
            messages = await build_context(rental, event, db)
            ai_reply = await call_llm(messages)

    sent = await waha_client.send_text(event.session_id, event.group_id, ai_reply)
    if not sent:
        logger.error("waha_ws_reply_send_failed", **event.log_fields())
        await _save_message_event(event, None)
        return

    await _save_message_event(event, ai_reply)
    logger.info("waha_ws_reply_sent", reply_chars=len(ai_reply), **event.log_fields())

    if event.message_text and ai_reply:
        task = asyncio.create_task(
            _extract_memory_background(binding.rental_id, event.message_text, ai_reply)
        )
        task.add_done_callback(
            lambda t: logger.error("waha_ws_memory_task_failed", error=str(t.exception()), **event.log_fields())
            if t.exception()
            else logger.info("waha_ws_memory_task_done", **event.log_fields())
        )

    if event.message_text:
        reminder_task = asyncio.create_task(
            _extract_and_save_reminder(
                binding.rental_id, event.group_id, event.sender_id, event.message_text,
                media_url=event.media_url, media_mime=event.media_mime,
            )
        )
        reminder_task.add_done_callback(
            lambda t: logger.error("waha_ws_reminder_task_failed", error=str(t.exception()), **event.log_fields())
            if t.exception()
            else logger.info("waha_ws_reminder_task_done", **event.log_fields())
        )


def build_ws_url(client: WAHAClient) -> str:
    base_url = client.base_url.rstrip("/")
    if base_url.startswith("https://"):
        ws_url = base_url.replace("https://", "wss://", 1) + "/ws"
    else:
        ws_url = base_url.replace("http://", "ws://", 1) + "/ws"

    params = {"session": "default", "events": "message"}
    if client.headers.get("X-Api-Key"):
        params["x-api-key"] = client.headers["X-Api-Key"]
    return f"{ws_url}?{urlencode(params)}"


async def websocket_listener(client: WAHAClient = waha_client, stop_event: asyncio.Event | None = None) -> None:
    import websockets

    full_url = build_ws_url(client)
    reconnect_delay = 2
    logger.info("waha_ws_listener_start", url=full_url.replace(settings.WAHA_API_KEY, "***") if settings.WAHA_API_KEY else full_url)

    while stop_event is None or not stop_event.is_set():
        try:
            async with websockets.connect(full_url, ping_interval=20, ping_timeout=20) as ws:
                reconnect_delay = 2
                logger.info("waha_ws_connected")
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("waha_ws_invalid_json", raw=raw[:500] if isinstance(raw, str) else str(raw)[:500])
                        continue

                    event_name = data.get("event", "")
                    if event_name not in ("message", "message.any"):
                        logger.info("waha_ws_skip_event", event_name=event_name)
                        continue

                    session_id = data.get("session") or "default"
                    payload = data.get("payload") or data.get("data") or {}
                    if not isinstance(payload, dict):
                        logger.warning("waha_ws_invalid_payload", event_name=event_name)
                        continue

                    # Debug: log raw payload fields
                    logger.info("waha_ws_raw_event", event_name=event_name, payload_keys=list(payload.keys()), msg_type=repr(payload.get("type")), has_body=bool(payload.get("body")), from_me=payload.get("fromMe"))

                    try:
                        await handle_inbound_message(payload, session_id=session_id)
                    except Exception as exc:
                        logger.error("waha_ws_message_handle_failed", error=str(exc), event_name=event_name)

        except asyncio.CancelledError:
            logger.info("waha_ws_listener_cancelled")
            raise
        except Exception as exc:
            logger.error("waha_ws_connection_error", error=str(exc), reconnect_delay=reconnect_delay)
            try:
                await asyncio.wait_for(asyncio.sleep(reconnect_delay), timeout=reconnect_delay + 1)
            except asyncio.CancelledError:
                logger.info("waha_ws_listener_cancelled")
                raise
            reconnect_delay = min(30, reconnect_delay * 2)

    logger.info("waha_ws_listener_stopped")


async def run() -> None:
    from app.core.logging import configure_logging
    from app.core.redis import get_redis_pool

    configure_logging()
    await get_redis_pool()
    await asyncio.gather(
        websocket_listener(waha_client),
        _reminder_scheduler_loop(),
    )


if __name__ == "__main__":
    asyncio.run(run())
