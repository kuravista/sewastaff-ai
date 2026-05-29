from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text as sql_text, desc
from app.schemas.normalized_event import NormalizedEvent
from app.models.rental_instance import RentalInstance
from app.models.reminder import Reminder
from app.models.staff_template import StaffTemplate
from app.models.message_event import MessageEvent
from app.models.staff_memory import StaffMemory
from app.models.staff_identity_memory import StaffIdentityMemory
from app.models.knowledge_item import KnowledgeItem
from app.services.role_compiler import compile_prompt
from app.services.embedding_service import get_embedding
from app.core.logging import get_logger

logger = get_logger(__name__)


async def build_context(
    rental: RentalInstance,
    current_event: NormalizedEvent,
    db: AsyncSession,
) -> list[dict]:
    # 1. Fetch template
    result = await db.execute(
        select(StaffTemplate).where(StaffTemplate.id == rental.template_id)
    )
    template = result.scalars().first()
    if not template:
        # Fallback if something is very wrong
        system_prompt = "You are a helpful assistant."
    else:
        # Ensure we pass the right traits
        traits = rental.custom_traits
        if not traits:
            traits = {}
            
        system_prompt = compile_prompt(
            template_name=template.name,
            specialty=template.specialty,
            base_prompt=template.base_prompt,
            traits=traits,
        )

    # 2. Identity Memory (ALWAYS inject — small, curated)
    try:
        identity_res = await db.execute(
            select(StaffIdentityMemory)
            .where(
                StaffIdentityMemory.rental_id == rental.id,
                StaffIdentityMemory.confirmed == True,
            )
            .order_by(StaffIdentityMemory.importance.desc())
        )
        identity_items = identity_res.scalars().all()
        if identity_items:
            system_prompt += "\n\n## Identitas Bisnis & Preferensi Owner:\n"
            for item in identity_items:
                system_prompt += f"- [{item.category}] {item.key}: {item.value}\n"
    except Exception as e:
        logger.warning("identity_memory_fetch_failed", error=str(e))

    # 3. Semantic Retrieval for staff_memories (pgvector if available, fallback to recency)
    query_text = current_event.message_text or ""
    memories = []
    
    if query_text and len(query_text) > 3:
        try:
            query_embedding = await get_embedding(query_text)
            if query_embedding:
                # pgvector cosine similarity search
                mem_res = await db.execute(
                    sql_text(
                        """SELECT id, type, content, source, confidence,
                                1 - (embedding <=> CAST(:query_vec AS vector)) as similarity
                           FROM staff_memories
                           WHERE rental_id = :rental_id AND embedding IS NOT NULL
                           ORDER BY embedding <=> CAST(:query_vec AS vector)
                           LIMIT 15"""
                    ),
                    {"query_vec": str(query_embedding), "rental_id": str(rental.id)}
                )
                rows = mem_res.fetchall()
                memories = [
                    {"type": row.type, "content": row.content, "similarity": row.similarity}
                    for row in rows
                ]
        except Exception as e:
            await db.rollback()
            logger.warning("semantic_memory_search_failed", error=str(e))
    
    # Fallback: recency-based if no semantic results
    if not memories:
        mem_res = await db.execute(
            select(StaffMemory)
            .where(StaffMemory.rental_id == rental.id)
            .order_by(StaffMemory.created_at.desc())
            .limit(30)
        )
        memories = [
            {"type": m.type, "content": m.content}
            for m in mem_res.scalars().all()
        ]

    if memories:
        system_prompt += "\n\n## Memory Pelanggan:\n"
        for m in memories:
            system_prompt += f"- [{m['type']}] {m['content']}\n"

    # 4. Fetch Knowledge
    know_res = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.rental_id == rental.id, KnowledgeItem.status == 'approved')
        .order_by(KnowledgeItem.created_at.desc())
        .limit(20)
    )
    knowledges = know_res.scalars().all()
    if knowledges:
        system_prompt += "\n\n## Knowledge Base Tambahan:\n"
        for k in knowledges:
            if k.summary:
                system_prompt += f"- {k.summary}\n"

    # 5. Fetch reminders (pending + recent sent/cancelled) for this rental/group only
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    now_utc = datetime.now(timezone.utc)
    rem_res = await db.execute(
        select(Reminder)
        .where(
            Reminder.rental_id == rental.id,
            Reminder.group_id == current_event.group_id,
            Reminder.status.in_(["pending", "sent", "cancelled"]),
            Reminder.fire_at >= now_utc - timedelta(days=7),
        )
        .order_by(Reminder.fire_at.asc())
        .limit(30)
    )
    reminders = rem_res.scalars().all()
    if reminders:
        tz = ZoneInfo("Asia/Jakarta")
        system_prompt += "\n\n## Reminder untuk grup ini (data aktual dari database):\n"
        for rm in reminders:
            fire_local = rm.fire_at.astimezone(tz).strftime("%d %b %Y %H:%M WIB") if rm.fire_at else "?"
            system_prompt += f"- [{rm.status}] {rm.title} — {fire_local}"
            if rm.recurrence:
                system_prompt += f" — berulang: {rm.recurrence}"
            system_prompt += "\n"
        system_prompt += "Jika user bertanya reminder apa saja, jam berapa, atau reminder tertentu, jawab HANYA berdasarkan daftar ini. Jangan bilang tanya tim.\n"

    messages = [{"role": "system", "content": system_prompt}]

    # 6. Fetch History (working memory — recent chat)
    hist_res = await db.execute(
        select(MessageEvent)
        .where(MessageEvent.group_id == current_event.group_id)
        .order_by(MessageEvent.timestamp.desc())
        .limit(20)
    )
    recent_events = hist_res.scalars().all()
    # Reverse to chronological
    recent_events.reverse()
    
    for evt in recent_events:
        role = "assistant" if evt.is_from_me else "user"
        messages.append({"role": role, "content": evt.content})
    
    b64_image = getattr(current_event, "_b64_image_data", None)
    if b64_image and current_event.media_mime:
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{current_event.media_mime};base64,{b64_image}"
                },
            },
            {
                "type": "text",
                "text": current_event.message_text or "Tolong analisis gambar ini.",
            },
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append(
            {"role": "user", "content": current_event.message_text or ""}
        )
        
    return messages
