import base64
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx

from app.models.knowledge_item import KnowledgeItem
from app.services.llm_client import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

async def process_knowledge_item(item_id: UUID, db: AsyncSession) -> None:
    """Process a pending knowledge item - extract/summarize content."""
    try:
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        item = result.scalars().first()
        if not item or item.status != "pending":
            return

        if item.type == "link" and item.source_url:
            await _process_link(item, db)
        elif item.type == "image" and item.source_url:
            await _process_image(item, db)
        elif item.type == "text" and item.content:
            await _process_text(item, db)
        else:
            logger.warning("knowledge_item_unprocessable", item_id=str(item_id), type=item.type)
            item.status = "rejected"
            await db.commit()
            
    except Exception as e:
        logger.error("knowledge_processing_failed", item_id=str(item_id), error=str(e))
        try:
            await db.rollback()
        except Exception:
            pass


async def _process_link(item: KnowledgeItem, db: AsyncSession) -> None:
    """Fetch URL content, extract text, summarize."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(item.source_url)
        resp.raise_for_status()
        raw_text = resp.text[:3000]

    prompt = f"""Ringkas konten berikut menjadi poin-poin penting yang relevan untuk customer service.
Konten:
{raw_text}

Return ringkasan singkat dalam Bahasa Indonesia, maksimal 200 kata."""

    summary = await call_llm([{"role": "user", "content": prompt}], model_key="fallback")
    item.summary = summary
    item.status = "approved"
    await db.commit()


async def _process_image(item: KnowledgeItem, db: AsyncSession) -> None:
    """Download image, use vision LLM to extract product info."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(item.source_url)
        resp.raise_for_status()
        b64 = base64.b64encode(resp.content).decode()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}"
                    }
                },
                {
                    "type": "text",
                    "text": "Deskripsikan produk/info dalam gambar ini secara singkat dalam Bahasa Indonesia. Maksimal 200 kata."
                }
            ]
        }
    ]
    summary = await call_llm(messages, model_key="fallback")
    item.summary = summary
    item.status = "approved"
    await db.commit()


async def _process_text(item: KnowledgeItem, db: AsyncSession) -> None:
    """Summarize/clean text content."""
    prompt = f"""Ringkas konten berikut menjadi poin-poin penting yang relevan untuk customer service.
Konten:
{item.content}

Return ringkasan singkat dalam Bahasa Indonesia, maksimal 200 kata."""

    summary = await call_llm([{"role": "user", "content": prompt}], model_key="fallback")
    item.summary = summary
    item.status = "approved"
    await db.commit()
