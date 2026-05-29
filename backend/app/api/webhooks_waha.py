from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from arq import create_pool
from arq.connections import RedisSettings

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.config import settings
from app.core.logging import get_logger
from app.models.group_binding import GroupBinding
from app.models.rental_instance import RentalInstance
from app.schemas.waha_event import normalize_waha_event
from app.schemas.normalized_event import NormalizedEvent

logger = get_logger(__name__)
router = APIRouter(tags=["webhooks"])


def normalize_waha_event_local(payload: dict, session: str) -> NormalizedEvent | None:
    return normalize_waha_event(payload, session)


async def enqueue_handle_message(event: NormalizedEvent, rental_id: str | None, canned_reply: bool):
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis_pool.enqueue_job(
        "handle_message",
        event.model_dump(mode="json"),
        rental_id=str(rental_id) if rental_id else "",
        canned_reply=canned_reply,
    )


# ── group.join handler ─────────────────────────────────────────────


async def handle_group_join(payload: dict, db: AsyncSession):
    """Process a WAHA group.v2.join webhook event.

    WAHA v2 event format:
    {"event": "group.v2.join", "session": "default", "payload": {"id": "xxx@g.us", ...}}
    Old format:
    {"event": "group.join", "session": "default", "data": {"id": "xxx@g.us", "name": "Group Name"}}
    """
    data = payload.get("payload") or payload.get("data", {})
    # GoWS group.v2.join payload may have JID instead of id
    group_id = data.get("JID") or data.get("id", "")
    group_name = data.get("Name") or data.get("name") or data.get("subject")

    if not group_id or not group_id.endswith("@g.us"):
        logger.warning("group_join_missing_id", payload=payload)
        return {"status": "ignored"}

    # Find pending binding with matching group_id, or any pending binding
    result = await db.execute(
        select(GroupBinding).where(GroupBinding.status == "pending")
    )
    pending = result.scalars().all()

    matched = None
    for b in pending:
        if b.group_id == group_id:
            matched = b
            break

    # If no group_id match, try matching by invite_link code
    if not matched:
        for b in pending:
            if b.invite_link:
                # Can't reliably match invite_link to group_id without extra info
                # Assign first pending without a group_id
                if not b.group_id:
                    matched = b
                    break

    if not matched:
        # Check if there's already a binding with this group_id (active)
        result = await db.execute(
            select(GroupBinding).where(GroupBinding.group_id == group_id)
        )
        existing = result.scalars().first()
        if existing:
            logger.info("group_join_already_bound", group_id=group_id)
            return {"status": "already_bound"}
        logger.info("group_join_no_pending_binding", group_id=group_id)
        return {"status": "ignored"}

    from datetime import datetime, timezone

    matched.group_id = group_id
    matched.group_name = group_name
    matched.status = "active"
    matched.joined_at = datetime.now(timezone.utc)

    # Update rental status
    result = await db.execute(
        select(RentalInstance).where(RentalInstance.id == matched.rental_id)
    )
    rental = result.scalars().first()
    if rental and rental.status == "trial":
        rental.status = "active"

    await db.commit()

    logger.info(
        "group_join_binding_activated",
        group_id=group_id,
        group_name=group_name,
        rental_id=str(matched.rental_id),
    )
    return {"status": "activated", "rental_id": str(matched.rental_id)}


# ── Main webhook endpoint ──────────────────────────────────────────


@router.post("/webhooks/waha")
async def waha_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.json()
    session = payload.get("session", "default")

    # Handle group join events before normalization.
    # WAHA current events use group.v2.join; group.join is deprecated.
    event_name = payload.get("event", "")
    if event_name in ("group.join", "group.v2.join"):
        return await handle_group_join(payload, db)

    logger.info("waha_webhook_received", event_name=event_name, session=session)

    event = normalize_waha_event_local(payload, session)
    if event is None:
        return {"status": "ignored"}

    if event.is_from_me:
        return {"status": "ignored"}

    redis = await get_redis()
    dedup_key = f"dedup:{event.event_id}"
    was_set = await redis.set(dedup_key, "1", ex=3600, nx=True)
    if not was_set:
        logger.info("duplicate_skipped", **event.log_fields())
        return {"status": "duplicate"}

    if event.message_type in ("sticker", "unknown"):
        return {"status": "ignored"}

    if event.message_type in ("document", "audio", "video"):
        await enqueue_handle_message(event, rental_id=None, canned_reply=True)
        return {"status": "queued"}

    result = await db.execute(select(GroupBinding).where(GroupBinding.group_id == event.group_id))
    binding = result.scalars().first()
    if not binding:
        logger.info("no_binding", **event.log_fields())
        return {"status": "ignored"}

    result = await db.execute(select(RentalInstance).where(RentalInstance.id == binding.rental_id))
    rental = result.scalars().first()
    if not rental or rental.status not in ("trial", "active"):
        logger.info("rental_inactive", rental_id=str(binding.rental_id), **event.log_fields())
        return {"status": "ignored"}

    await enqueue_handle_message(event, rental_id=str(binding.rental_id), canned_reply=False)
    logger.info("enqueue_success", rental_id=str(binding.rental_id), **event.log_fields())
    return {"status": "queued"}
