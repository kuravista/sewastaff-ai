import json
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.services.llm_client import call_llm
from app.services.embedding_service import get_embedding
from app.models.staff_memory import StaffMemory
from app.models.staff_identity_memory import StaffIdentityMemory
from app.models.staff_episode import StaffEpisode
from app.core.logging import get_logger

logger = get_logger(__name__)

# Valid categories for extracted facts
VALID_CATEGORIES = {"preference", "fact", "event", "insight", "procedure"}

async def extract_and_save_memory(
    rental_id: UUID,
    user_msg: str,
    ai_reply: str,
    db: AsyncSession,
    group_id: str | None = None,
    actor_id: str | None = None,
    source_event_id: str | None = None,
) -> None:
    """Call a cheap LLM to extract memorable facts. Enhanced V2 with classification.
    
    Non-blocking best-effort. Saves to:
    - staff_memories (always, backward compatible)
    - staff_identity_memories (if is_identity=true)
    - staff_episodes (if type=event)
    """
    try:
        prompt = f"""Extrak fakta penting dari percakapan ini. Return JSON saja.
Pesan user: {user_msg}
Balasan AI: {ai_reply}

Return format:
{{"facts": [
  {{
    "type": "preference|fact|complaint",
    "content": "...",
    "category": "preference|fact|event|insight|procedure",
    "importance": 0.0,
    "is_identity": false,
    "key": "optional_short_key"
  }},
  ...
]}}

Aturan:
- Hanya extract kalau ada fakta jelas (nama, preferensi, keluhan, info produk, prosedur, insight bisnis)
- Kalau tidak ada fakta, return {{"facts": []}}
- Maksimal 3 fakta per exchange
- Content singkat, max 100 karakter
- importance: 0.0-1.0 (seberapa penting untuk bisnis, 1.0 = kritis)
- category: "preference" (preferensi owner/customer), "fact" (fakta umum), "event" (kejadian/interaksi penting), "insight" (insight bisnis), "procedure" (SOP/cara kerja)
- is_identity: true jika ini adalah preferensi inti owner atau aturan bisnis yang harus selalu diingat
- key: singkat 1-3 kata hanya jika is_identity=true (misal: "tone", "target_customer", "jam_kerja")
- HANYA return JSON, tidak ada teks lain"""

        messages = [{"role": "user", "content": prompt}]
        
        reply = await call_llm(messages, model_key="fallback")
        
        # Parse JSON
        reply = reply.strip()
        if reply.startswith("```json"):
            reply = reply[7:]
            if reply.endswith("```"):
                reply = reply[:-3]
            reply = reply.strip()
        elif reply.startswith("```"):
            reply = reply[3:]
            if reply.endswith("```"):
                reply = reply[:-3]
            reply = reply.strip()
            
        data = json.loads(reply)
        facts = data.get("facts", [])
        
        has_changes = False
        
        for fact in facts:
            fact_type = fact.get("type")
            content = fact.get("content")
            if not content:
                continue
                
            content = content[:100]
            category = fact.get("category", "fact")
            if category not in VALID_CATEGORIES:
                category = "fact"
            importance = fact.get("importance", 0.5)
            try:
                importance = max(0.0, min(1.0, float(importance)))
            except (TypeError, ValueError):
                importance = 0.5
            is_identity = bool(fact.get("is_identity", False))
            key = fact.get("key", "")
            
            embedding_vec = await get_embedding(content)

            # 1. Always save to staff_memories (backward compatible)
            if fact_type in ("preference", "fact", "complaint") and content:
                if embedding_vec:
                    from sqlalchemy import text as sa_text
                    await db.execute(sa_text(
                        "INSERT INTO staff_memories "
                        "(id, rental_id, type, content, source, confidence, embedding) "
                        "VALUES (gen_random_uuid(), :rid, :type, :content, :source, :conf, CAST(:emb AS vector))"
                    ), {
                        "rid": str(rental_id),
                        "type": fact_type,
                        "content": content,
                        "source": "chat_extraction",
                        "conf": 0.9,
                        "emb": str(embedding_vec)
                    })
                else:
                    new_memory = StaffMemory(
                        rental_id=rental_id,
                        type=fact_type,
                        content=content,
                        source="chat_extraction",
                        confidence=0.9,
                        embedding=None,
                    )
                    db.add(new_memory)
                has_changes = True
            
            # 2. If identity memory, upsert to staff_identity_memories
            if is_identity and key:
                existing = await db.execute(
                    select(StaffIdentityMemory).where(
                        StaffIdentityMemory.rental_id == rental_id,
                        StaffIdentityMemory.key == key,
                    )
                )
                existing_item = existing.scalars().first()
                if existing_item:
                    # Just update fields without embedding for identity for now
                    existing_item.value = content
                    existing_item.importance = importance
                    existing_item.category = category
                    existing_item.updated_at = datetime.now(timezone.utc)
                    has_changes = True
                else:
                    identity_mem = StaffIdentityMemory(
                        rental_id=rental_id,
                        category=category,
                        key=key,
                        value=content,
                        importance=importance,
                        source="extracted",
                        confirmed=True,
                    )
                    db.add(identity_mem)
                    has_changes = True
            
            # 3. If event-type, create staff_episode
            if category == "event" and content:
                if embedding_vec:
                    from sqlalchemy import text as sa_text
                    await db.execute(sa_text(
                        "INSERT INTO staff_episodes "
                        "(id, rental_id, group_id, event_type, actor_id, summary, importance, embedding, source_event_id, occurred_at) "
                        "VALUES (gen_random_uuid(), :rid, :gid, :et, :aid, :summ, :imp, CAST(:emb AS vector), :seid, :oat)"
                    ), {
                        "rid": str(rental_id),
                        "gid": group_id or "",
                        "et": "customer_interaction",
                        "aid": actor_id or "",
                        "summ": content,
                        "imp": importance,
                        "emb": str(embedding_vec),
                        "seid": source_event_id,
                        "oat": datetime.now(timezone.utc),
                    })
                else:
                    episode = StaffEpisode(
                        rental_id=rental_id,
                        group_id=group_id or "",
                        event_type="customer_interaction",
                        actor_id=actor_id or "",
                        summary=content,
                        importance=importance,
                        embedding=None,
                        source_event_id=source_event_id,
                        occurred_at=datetime.now(timezone.utc),
                    )
                    db.add(episode)
                has_changes = True; 
                # ORM model still declares embedding as String while DB is vector(1536), so vector writes must use raw SQL cast.
        
        if has_changes:
            await db.commit()
            
    except Exception as e:
        logger.error("memory_extraction_failed", error=str(e), rental_id=str(rental_id))
        # Best effort, do not crash main pipeline
        try:
            await db.rollback()
        except Exception:
            pass
