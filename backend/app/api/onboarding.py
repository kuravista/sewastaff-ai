from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.models.tenant import Tenant
from app.models.rental_instance import RentalInstance
from app.models.staff_template import StaffTemplate
from app.models.group_binding import GroupBinding
from app.services.role_compiler import compile_prompt

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

class FAQItem(BaseModel):
    q: str
    a: str

class StartOnboardingRequest(BaseModel):
    email: EmailStr
    bisnis_name: str
    bisnis_desc: str
    produk_jasa: str
    jam_operasional: str
    faq: list[FAQItem]
    template_slug: str

@router.post("/start")
async def start_onboarding(req: StartOnboardingRequest, db: AsyncSession = Depends(get_db)):
    # Create Tenant (or get by email)
    result = await db.execute(select(Tenant).where(Tenant.email == req.email))
    tenant = result.scalars().first()
    if not tenant:
        tenant = Tenant(email=req.email, name=req.bisnis_name)
        db.add(tenant)
        await db.flush()

    # Get template
    result = await db.execute(select(StaffTemplate).where(StaffTemplate.slug == req.template_slug))
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Compile prompt
    traits = {
        "bisnis_name": req.bisnis_name,
        "bisnis_desc": req.bisnis_desc,
        "produk_jasa": req.produk_jasa,
        "jam_operasional": req.jam_operasional,
        "faq": [f.model_dump() for f in req.faq]
    }
    compiled_prompt = compile_prompt(
        template_name=template.name,
        specialty=template.specialty,
        base_prompt=template.base_prompt,
        traits=traits
    )
    traits["compiled_prompt"] = compiled_prompt

    # Create RentalInstance
    rental = RentalInstance(
        tenant_id=tenant.id,
        template_id=template.id,
        status="trial",
        custom_traits=traits
    )
    db.add(rental)
    await db.commit()

    phone = getattr(settings, "WAHA_PHONE_NUMBER", "+6281234567890")
    return {
        "rental_id": str(rental.id),
        "waha_phone": phone,
        "invite_instructions": f"Buat grup WhatsApp baru → invite nomor ini: {phone}. Setelah Staff AI bergabung, ia akan aktif otomatis."
    }

@router.get("/status/{rental_id}")
async def get_onboarding_status(rental_id: str, db: AsyncSession = Depends(get_db)):
    try:
        rid = uuid.UUID(rental_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rental_id")

    result = await db.execute(select(RentalInstance).where(RentalInstance.id == rid))
    rental = result.scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    # Get binding
    result = await db.execute(select(GroupBinding).where(GroupBinding.rental_id == rental.id))
    binding = result.scalars().first()

    group_id_masked = None
    bound_at = None
    if binding:
        if len(binding.group_id) > 4:
            group_id_masked = "****" + binding.group_id[-4:]
        else:
            group_id_masked = binding.group_id
        bound_at = binding.bound_at

    return {
        "status": rental.status,
        "group_id": group_id_masked,
        "bound_at": bound_at
    }
