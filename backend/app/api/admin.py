import asyncio
import base64
import json
from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.models.group_binding import GroupBinding
from app.models.knowledge_item import KnowledgeItem
from app.models.message_event import MessageEvent
from app.models.rental_instance import RentalInstance
from app.models.reminder import Reminder
from app.models.staff_memory import StaffMemory
from app.models.staff_template import StaffTemplate
from app.models.tenant import Tenant
from app.services.knowledge_processor import process_knowledge_item

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _auth(request: Request):
    # Accept X-Admin-Token header for direct API/curl usage
    token = request.headers.get("X-Admin-Token")
    if token and token == settings.ADMIN_SECRET_KEY:
        return
    # If request comes through Caddy (has X-Forwarded-For), Caddy basic_auth already validated
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return  # Caddy already authenticated via basic_auth
    raise HTTPException(status_code=401, detail="Unauthorized")


def _to_dict(v):
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return dict(v)


def _dt(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _rental_out(r: RentalInstance):
    return {
        "id": str(r.id),
        "tenant_id": str(r.tenant_id),
        "template_id": str(r.template_id),
        "custom_traits": _to_dict(r.custom_traits),
        "status": r.status,
        "started_at": _dt(r.started_at),
        "expires_at": _dt(r.expires_at),
    }


def _template_out(t: StaffTemplate):
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "specialty": t.specialty,
        "base_prompt": t.base_prompt,
        "avatar_emoji": t.avatar_emoji,
        "price_monthly_idr": t.price_monthly_idr,
        "is_active": t.is_active,
    }


def _memory_out(m: StaffMemory):
    return {
        "id": str(m.id),
        "rental_id": str(m.rental_id),
        "type": m.type,
        "content": m.content,
        "source": m.source,
        "confidence": m.confidence,
        "created_at": _dt(m.created_at),
    }


def _knowledge_out(k: KnowledgeItem):
    return {
        "id": str(k.id),
        "rental_id": str(k.rental_id),
        "type": k.type,
        "source_url": k.source_url,
        "content": k.content,
        "summary": k.summary,
        "status": k.status,
        "created_at": _dt(k.created_at),
    }


class TraitsBody(BaseModel):
    bisnis_name: str | None = None
    bisnis_desc: str | None = None
    produk_jasa: str | None = None
    jam_operasional: str | None = None
    faq: list[dict] | None = None


class StatusBody(BaseModel):
    status: str


class TemplateBody(BaseModel):
    name: str | None = None
    specialty: str | None = None
    base_prompt: str | None = None
    avatar_emoji: str | None = None
    price_monthly_idr: int | None = None
    is_active: bool | None = None


class KnowledgeBody(BaseModel):
    type: str
    content: str | None = None
    source_url: str | None = None


class KnowledgeStatusBody(BaseModel):
    status: str


# ── WAHA Proxy ─────────────────────────────────────────────

def _waha_headers():
    return {"X-Api-Key": settings.WAHA_API_KEY}


@router.get("/waha/sessions")
async def waha_list_sessions(request: Request):
    _auth(request)
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{settings.WAHA_BASE_URL}/api/sessions?all=true", headers=_waha_headers())
        return r.json()


@router.post("/waha/sessions/{name}/start")
async def waha_start_session(name: str, request: Request):
    _auth(request)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{settings.WAHA_BASE_URL}/api/sessions/{name}/start", headers=_waha_headers())
        return r.json()


@router.post("/waha/sessions/{name}/stop")
async def waha_stop_session(name: str, request: Request):
    _auth(request)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{settings.WAHA_BASE_URL}/api/sessions/{name}/stop", headers=_waha_headers())
        return r.json()


@router.post("/waha/sessions/{name}/logout")
async def waha_logout_session(name: str, request: Request):
    _auth(request)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{settings.WAHA_BASE_URL}/api/sessions/{name}/logout",
            headers={**_waha_headers(), "Content-Type": "application/json"},
            json={"session": name},
        )
        return r.json()


@router.get("/waha/sessions/{name}/qr")
async def waha_get_qr(name: str, request: Request):
    _auth(request)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{settings.WAHA_BASE_URL}/api/{name}/auth/qr",
            headers={**_waha_headers()},
            params={"format": "image"},
        )
        if r.status_code != 200:
            return {"error": "QR not available", "status": r.status_code}
        b64 = base64.b64encode(r.content).decode()
        return {"qr_base64": f"data:image/png;base64,{b64}"}


@router.post("/waha/sessions/{name}/request-code")
async def waha_request_code(name: str, body: dict, request: Request):
    _auth(request)
    phone = body.get("phone", "").replace("@c.us", "").replace("@s.whatsapp.net", "")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{settings.WAHA_BASE_URL}/api/{name}/auth/request-code",
            headers={**_waha_headers(), "Content-Type": "application/json"},
            json={"phoneNumber": phone},
        )
        return r.json()


@router.delete("/waha/sessions/{name}")
async def waha_delete_session(name: str, request: Request):
    _auth(request)
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(f"{settings.WAHA_BASE_URL}/api/sessions/{name}", headers=_waha_headers())
        return {"status": "deleted"}


async def _process_knowledge_bg(item_id: UUID):
    async with SessionLocal() as db:
        await process_knowledge_item(item_id, db)


@router.get("/rentals")
async def list_rentals(request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    mem_count = select(StaffMemory.rental_id, func.count(StaffMemory.id).label("count")).group_by(StaffMemory.rental_id).subquery()
    know_count = select(KnowledgeItem.rental_id, func.count(KnowledgeItem.id).label("count")).group_by(KnowledgeItem.rental_id).subquery()
    result = await db.execute(
        select(RentalInstance, Tenant, StaffTemplate, GroupBinding, mem_count.c.count, know_count.c.count)
        .join(Tenant, Tenant.id == RentalInstance.tenant_id)
        .join(StaffTemplate, StaffTemplate.id == RentalInstance.template_id)
        .outerjoin(GroupBinding, GroupBinding.rental_id == RentalInstance.id)
        .outerjoin(mem_count, mem_count.c.rental_id == RentalInstance.id)
        .outerjoin(know_count, know_count.c.rental_id == RentalInstance.id)
        .order_by(RentalInstance.started_at.desc().nullslast())
    )
    rows = []
    for rental, tenant, template, binding, memories, knowledge in result.all():
        rows.append({
            **_rental_out(rental),
            "tenant": {"id": str(tenant.id), "email": tenant.email, "name": tenant.name, "telegram_chat_id": tenant.telegram_chat_id},
            "template": _template_out(template),
            "group_binding": None if not binding else {"id": str(binding.id), "group_id": binding.group_id, "group_name": binding.group_name, "session_id": binding.session_id, "bound_at": _dt(binding.bound_at)},
            "is_bound": binding is not None,
            "memory_count": memories or 0,
            "knowledge_count": knowledge or 0,
        })
    return rows


@router.get("/rentals/{rental_id}")
async def rental_detail(rental_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    rental = (await db.execute(select(RentalInstance).where(RentalInstance.id == rental_id))).scalars().first()
    if not rental:
        raise HTTPException(404, "Rental not found")
    memories = (await db.execute(select(StaffMemory).where(StaffMemory.rental_id == rental_id).order_by(StaffMemory.created_at.desc()))).scalars().all()
    knowledge = (await db.execute(select(KnowledgeItem).where(KnowledgeItem.rental_id == rental_id).order_by(KnowledgeItem.created_at.desc()))).scalars().all()
    return {**_rental_out(rental), "memories": [_memory_out(m) for m in memories], "knowledge_items": [_knowledge_out(k) for k in knowledge]}


@router.put("/rentals/{rental_id}/traits")
async def update_traits(rental_id: UUID, body: TraitsBody, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    traits = body.model_dump(exclude_none=True)
    result = await db.execute(text("UPDATE rental_instances SET custom_traits = CAST(:traits AS jsonb) WHERE id = :id RETURNING *"), {"traits": json.dumps(traits), "id": str(rental_id)})
    row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Rental not found")
    await db.commit()
    return {"id": str(row["id"]), "custom_traits": _to_dict(row["custom_traits"]), "status": row["status"]}


@router.patch("/rentals/{rental_id}/status")
async def update_status(rental_id: UUID, body: StatusBody, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    if body.status not in ("trial", "active", "expired", "suspended"):
        raise HTTPException(400, "Invalid status")
    result = await db.execute(update(RentalInstance).where(RentalInstance.id == rental_id).values(status=body.status).returning(RentalInstance))
    rental = result.scalars().first()
    if not rental:
        raise HTTPException(404, "Rental not found")
    await db.commit()
    return _rental_out(rental)


@router.get("/templates")
async def list_templates(request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    templates = (await db.execute(select(StaffTemplate).order_by(StaffTemplate.slug))).scalars().all()
    return [_template_out(t) for t in templates]


@router.put("/templates/{template_id}")
async def update_template(template_id: UUID, body: TemplateBody, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    vals = body.model_dump(exclude_none=True)
    if not vals:
        raise HTTPException(400, "No fields to update")
    result = await db.execute(update(StaffTemplate).where(StaffTemplate.id == template_id).values(**vals).returning(StaffTemplate))
    template = result.scalars().first()
    if not template:
        raise HTTPException(404, "Template not found")
    await db.commit()
    return _template_out(template)


@router.get("/memory/{rental_id}")
async def list_memory(rental_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    memories = (await db.execute(select(StaffMemory).where(StaffMemory.rental_id == rental_id).order_by(StaffMemory.created_at.desc()))).scalars().all()
    return [_memory_out(m) for m in memories]


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    result = await db.execute(delete(StaffMemory).where(StaffMemory.id == memory_id).returning(StaffMemory.id))
    deleted = result.scalar()
    if not deleted:
        raise HTTPException(404, "Memory not found")
    await db.commit()
    return {"deleted": str(deleted)}


@router.get("/knowledge/{rental_id}")
async def list_knowledge(rental_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    items = (await db.execute(select(KnowledgeItem).where(KnowledgeItem.rental_id == rental_id).order_by(KnowledgeItem.created_at.desc()))).scalars().all()
    return [_knowledge_out(k) for k in items]


@router.post("/knowledge/{rental_id}")
async def create_knowledge(rental_id: UUID, body: KnowledgeBody, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    if body.type not in ("text", "link"):
        raise HTTPException(400, "Invalid type")
    item = KnowledgeItem(rental_id=rental_id, type=body.type, content=body.content, source_url=body.source_url, status="pending")
    db.add(item)
    await db.commit()
    await db.refresh(item)
    asyncio.create_task(_process_knowledge_bg(item.id))
    return _knowledge_out(item)


@router.patch("/knowledge/{item_id}/status")
async def update_knowledge_status(item_id: UUID, body: KnowledgeStatusBody, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    if body.status not in ("approved", "rejected"):
        raise HTTPException(400, "Invalid status")
    result = await db.execute(update(KnowledgeItem).where(KnowledgeItem.id == item_id).values(status=body.status).returning(KnowledgeItem))
    item = result.scalars().first()
    if not item:
        raise HTTPException(404, "Knowledge item not found")
    await db.commit()
    return _knowledge_out(item)


@router.delete("/knowledge/{item_id}")
async def delete_knowledge(item_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    result = await db.execute(delete(KnowledgeItem).where(KnowledgeItem.id == item_id).returning(KnowledgeItem.id))
    deleted = result.scalar()
    if not deleted:
        raise HTTPException(404, "Knowledge item not found")
    await db.commit()
    return {"deleted": str(deleted)}


@router.get("/system/stats")
async def system_stats(request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    total_rentals = await db.scalar(select(func.count(RentalInstance.id)))
    active_rentals = await db.scalar(select(func.count(RentalInstance.id)).where(RentalInstance.status == "active"))
    total_memories = await db.scalar(select(func.count(StaffMemory.id)))
    total_knowledge_items = await db.scalar(select(func.count(KnowledgeItem.id)))
    return {
        "total_rentals": total_rentals or 0,
        "active_rentals": active_rentals or 0,
        "total_memories": total_memories or 0,
        "total_knowledge_items": total_knowledge_items or 0,
    }


@router.get("/rentals/{rental_id}/messages")
async def rental_messages(rental_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    # Find GroupBinding for this rental to get group_id
    binding = (await db.execute(
        select(GroupBinding).where(GroupBinding.rental_id == rental_id)
    )).scalars().first()
    if not binding or not binding.group_id:
        return []
    # Query last 100 message_events for this group, then return chronological order
    result = await db.execute(
        select(MessageEvent)
        .where(MessageEvent.group_id == binding.group_id)
        .order_by(MessageEvent.timestamp.desc())
        .limit(100)
    )
    messages = list(reversed(result.scalars().all()))
    return [
        {
            "event_id": m.event_id,
            "sender_id": m.sender_id,
            "content": m.content,
            "is_from_me": m.is_from_me,
            "message_type": m.message_type,
            "timestamp": _dt(m.timestamp),
        }
        for m in messages
    ]


# ── Reminders ─────────────────────────────────────────────

@router.get("/rentals/{rental_id}/reminders")
async def list_reminders(rental_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    reminders = (await db.execute(
        select(Reminder)
        .where(Reminder.rental_id == rental_id)
        .order_by(Reminder.fire_at.asc())
    )).scalars().all()
    return [
        {
            "id": str(r.id),
            "rental_id": str(r.rental_id),
            "group_id": r.group_id,
            "title": r.title,
            "description": r.description,
            "fire_at": _dt(r.fire_at),
            "timezone": r.timezone,
            "status": r.status,
            "recurrence": r.recurrence,
            "sent_at": _dt(r.sent_at),
            "created_by": r.created_by,
            "created_at": _dt(r.created_at),
        }
        for r in reminders
    ]


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    # Cancel instead of hard delete — keeps audit trail
    result = await db.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id, Reminder.status == "pending")
        .values(status="cancelled")
        .returning(Reminder.id)
    )
    deleted = result.scalar()
    if not deleted:
        raise HTTPException(404, "Reminder not found or already processed")
    await db.commit()


# ── Role Requests (Demand-Driven) ────────────────────────────────

@router.get("/role-requests")
async def list_role_requests(request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    from app.services.search_cluster_service import get_role_requests
    return await get_role_requests(db)


@router.post("/role-requests/{cluster_id}/generate")
async def generate_role_draft(cluster_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    from app.services.search_cluster_service import generate_draft
    result = await generate_draft(cluster_id, db)
    if not result:
        raise HTTPException(400, "Failed to generate draft")
    return result


class ApproveRoleRequest(BaseModel):
    slug: str | None = None
    name: str | None = None
    specialty: str | None = None
    base_prompt: str | None = None
    avatar_emoji: str | None = None
    price_monthly_idr: int | None = None


@router.post("/role-requests/{cluster_id}/approve")
async def approve_role_request(cluster_id: str, payload: ApproveRoleRequest, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    from app.services.search_cluster_service import approve_role_request as _approve
    result = await _approve(cluster_id, payload.model_dump(exclude_none=True), db)
    if not result:
        raise HTTPException(400, "Failed to approve role request")
    return result


@router.delete("/role-requests/{cluster_id}/reject")
async def reject_role_request(cluster_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    from app.services.search_cluster_service import reject_role_request as _reject
    await _reject(cluster_id, db)
    return {"status": "rejected"}
