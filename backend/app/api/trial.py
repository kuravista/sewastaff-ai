from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
import asyncio
import uuid
import json

from app.core.database import get_db, SessionLocal
from app.core.redis import get_redis
from app.models.staff_template import StaffTemplate
from app.services.role_compiler import compile_prompt
from app.services.llm_client import call_llm
from app.services.memory_extractor import extract_and_save_memory

router = APIRouter(prefix="/api/trial", tags=["trial"])
TRIAL_DEMO_RENTAL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

async def _extract_trial_memory(trial_id: str, user_msg: str, ai_reply: str) -> None:
    async with SessionLocal() as db:
        await extract_and_save_memory(TRIAL_DEMO_RENTAL_ID, user_msg, ai_reply, db)

class StartTrialRequest(BaseModel):
    template_slug: str

class MessageTrialRequest(BaseModel):
    trial_id: str
    message: str

@router.post("/start")
async def start_trial(req: StartTrialRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StaffTemplate).where(StaffTemplate.slug == req.template_slug))
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    generic_traits = {
        "bisnis_name": "Bisnis Demo",
        "bisnis_desc": "Sebuah bisnis untuk demonstrasi",
        "produk_jasa": "Berbagai layanan",
        "jam_operasional": "24 Jam",
        "faq": []
    }
    
    system_prompt = compile_prompt(
        template_name=template.name,
        specialty=template.specialty,
        base_prompt=template.base_prompt,
        traits=generic_traits
    )

    trial_id = str(uuid.uuid4())
    redis = await get_redis()
    
    trial_data = {
        "slug": template.slug,
        "system_prompt": system_prompt,
        "history": [],
        "remaining": 10
    }
    await redis.setex(f"trial:{trial_id}", 3600, json.dumps(trial_data))

    return {
        "trial_id": trial_id,
        "staff_name": template.name,
        "avatar_emoji": template.avatar_emoji,
        "messages_remaining": 10
    }

@router.post("/message")
async def send_trial_message(req: MessageTrialRequest):
    redis = await get_redis()
    trial_key = f"trial:{req.trial_id}"
    raw_data = await redis.get(trial_key)
    
    if not raw_data:
        raise HTTPException(status_code=404, detail="Trial session not found or expired")
        
    trial_data = json.loads(raw_data)
    
    if trial_data["remaining"] <= 0:
        return {
            "reply": None,
            "messages_remaining": 0,
            "cta": "Aktifkan via WhatsApp — Rp99k/bulan",
            "cta_url": "/onboarding"
        }

    # Build context manually instead of using context_builder since we use simple list here
    messages = [{"role": "system", "content": trial_data["system_prompt"]}]
    for msg in trial_data["history"]:
        messages.append(msg)
    
    messages.append({"role": "user", "content": req.message})
    
    # Update history in redis immediately (optimistic)
    trial_data["history"].append({"role": "user", "content": req.message})
    
    try:
        reply = await call_llm(messages)
    except Exception as e:
        reply = "Maaf, sistem sedang mengalami kendala. Coba beberapa saat lagi."
        
    trial_data["history"].append({"role": "assistant", "content": reply})
    trial_data["remaining"] -= 1
    
    await redis.setex(trial_key, 3600, json.dumps(trial_data))
    
    asyncio.create_task(_extract_trial_memory(req.trial_id, req.message, reply))
    
    return {
        "reply": reply,
        "messages_remaining": trial_data["remaining"]
    }
