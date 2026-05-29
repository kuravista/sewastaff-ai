from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.staff_template import StaffTemplate

router = APIRouter(prefix="/api/staff", tags=["staff"])

FEATURES_MAP = {
    "hr": ["Screening CV", "Jadwal interview", "Follow-up kandidat"],
    "pa": ["Reminder", "Ringkasan harian", "To-do list"],
    "akuntansi": ["Catat transaksi", "Rekap laporan", "Reminder tagihan"],
    "cs": ["Jawab pertanyaan", "Follow-up pelanggan", "Keluhan pelanggan"],
    "sales": ["Follow-up lead", "Kirim penawaran", "Pipeline sales"],
}

class StaffTemplateResponse(BaseModel):
    slug: str
    name: str
    specialty: str
    avatarEmoji: str
    priceMonthlyIdr: int
    features: list[str]

    model_config = {"from_attributes": True}

@router.get("/", response_model=list[StaffTemplateResponse])
async def get_staff_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StaffTemplate).where(StaffTemplate.is_active == True))
    templates = result.scalars().all()
    
    response = []
    for t in templates:
        features = FEATURES_MAP.get(t.slug, [])
        response.append({
            "slug": t.slug,
            "name": t.name,
            "specialty": t.specialty,
            "avatarEmoji": t.avatar_emoji,
            "priceMonthlyIdr": t.price_monthly_idr,
            "features": features
        })
    return response

@router.get("/{slug}", response_model=StaffTemplateResponse)
async def get_staff_template(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StaffTemplate).where(StaffTemplate.slug == slug))
    template = result.scalars().first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    features = FEATURES_MAP.get(template.slug, [])
    return {
        "slug": template.slug,
        "name": template.name,
        "specialty": template.specialty,
        "avatarEmoji": template.avatar_emoji,
        "priceMonthlyIdr": template.price_monthly_idr,
        "features": features
    }
