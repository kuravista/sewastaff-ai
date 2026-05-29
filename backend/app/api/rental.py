import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.group_binding import GroupBinding
from app.models.rental_instance import RentalInstance
from app.models.staff_template import StaffTemplate
from app.models.tenant import Tenant
from app.services.waha_client import waha_client

logger = get_logger(__name__)
router = APIRouter(prefix="/api/rental", tags=["rental"])


class CreateRentalRequest(BaseModel):
    template_slug: str
    tenant_name: str
    tenant_phone: str


class BindGroupRequest(BaseModel):
    invite_link: str


def parse_rental_id(rental_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(rental_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rental_id")


def extract_invite_code(invite_link: str) -> str:
    parsed = urlparse(invite_link.strip())
    host = parsed.netloc.lower()
    if host not in {"chat.whatsapp.com", "www.chat.whatsapp.com"}:
        raise HTTPException(status_code=400, detail="Invalid WhatsApp invite link")

    code = parsed.path.strip("/").split("/")[0]
    if not code or not re.fullmatch(r"[A-Za-z0-9_-]{10,}", code):
        raise HTTPException(status_code=400, detail="Invalid WhatsApp invite code")
    return code


def extract_group_id(data: dict[str, Any]) -> str | None:
    candidates = [
        data.get("id"),
        data.get("groupId"),
        data.get("gid"),
        data.get("chatId"),
        data.get("jid"),
    ]
    nested = data.get("data")
    if isinstance(nested, dict):
        candidates.extend(
            [nested.get("id"), nested.get("groupId"), nested.get("gid"), nested.get("chatId"), nested.get("jid")]
        )

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.endswith("@g.us"):
            return candidate
    return None


def extract_group_name(data: dict[str, Any]) -> str | None:
    candidates = [data.get("Name"), data.get("name"), data.get("subject"), data.get("groupName")]
    nested = data.get("data")
    if isinstance(nested, dict):
        candidates.extend([nested.get("Name"), nested.get("name"), nested.get("subject"), nested.get("groupName")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def binding_response(binding: GroupBinding | None) -> dict[str, Any]:
    if not binding:
        return {
            "status": "unbound",
            "group_id": None,
            "group_name": None,
            "joined_at": None,
            "invite_link": None,
        }
    return {
        "status": binding.status,
        "group_id": binding.group_id,
        "group_name": binding.group_name,
        "joined_at": binding.joined_at,
        "invite_link": binding.invite_link,
    }


@router.post("/create")
async def create_rental(
    req: CreateRentalRequest,
    db: AsyncSession = Depends(get_db),
):
    # Find template by slug
    result = await db.execute(
        select(StaffTemplate).where(StaffTemplate.slug == req.template_slug)
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Staff template not found")

    # Find or create tenant by phone (use phone as email placeholder)
    tenant_email = f"wa:{req.tenant_phone}"
    result = await db.execute(
        select(Tenant).where(Tenant.email == tenant_email)
    )
    tenant = result.scalars().first()
    if not tenant:
        tenant = Tenant(
            email=tenant_email,
            name=req.tenant_name,
        )
        db.add(tenant)
        await db.flush()

    # Create rental instance
    rental = RentalInstance(
        tenant_id=tenant.id,
        template_id=template.id,
        status="active",
        custom_traits={
            "tenant_name": req.tenant_name,
            "tenant_phone": req.tenant_phone,
        },
    )
    db.add(rental)
    await db.commit()
    await db.refresh(rental)

    logger.info(
        "rental_created",
        rental_id=str(rental.id),
        template_slug=req.template_slug,
        tenant_name=req.tenant_name,
    )

    return {
        "rental_id": str(rental.id),
        "staff_name": template.name,
        "staff_emoji": template.avatar_emoji,
        "status": rental.status,
    }


@router.post("/{rental_id}/bind-group")
async def bind_group(
    rental_id: str,
    req: BindGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    rid = parse_rental_id(rental_id)
    result = await db.execute(select(RentalInstance).where(RentalInstance.id == rid))
    rental = result.scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    invite_code = extract_invite_code(req.invite_link)

    result = await db.execute(select(GroupBinding).where(GroupBinding.rental_id == rid))
    binding = result.scalars().first()
    if not binding:
        binding = GroupBinding(
            rental_id=rid,
            invite_link=req.invite_link,
            session_id="default",
            status="pending",
        )
        db.add(binding)
    else:
        binding.invite_link = req.invite_link
        binding.session_id = binding.session_id or "default"
        binding.status = "pending"

    await db.flush()

    try:
        join_data = await waha_client.join_group(invite_code)
    except httpx.HTTPStatusError as e:
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "message": "WAHA group join failed",
                "status_code": e.response.status_code,
                "body": e.response.text,
            },
        )
    except Exception as e:
        await db.commit()
        raise HTTPException(status_code=502, detail=f"WAHA group join failed: {str(e)}")

    group_id = extract_group_id(join_data)
    group_name = extract_group_name(join_data)
    now = datetime.now(timezone.utc)

    if group_id:
        binding.group_id = group_id
        binding.status = "active"
        binding.joined_at = now
        if rental.status == "trial":
            rental.status = "active"
        # Fetch group name from WAHA if not returned in join response
        if not group_name:
            try:
                info = await waha_client.get_group_info(group_id)
                group_name = info.get("Name") or info.get("subject") or info.get("name")
            except Exception:
                pass
        binding.group_name = group_name
    else:
        # WAHA may complete join asynchronously and emit group.join webhook later.
        binding.status = "pending"

    await db.commit()
    await db.refresh(binding)

    logger.info(
        "rental_group_bind_requested",
        rental_id=str(rid),
        group_id=binding.group_id,
        status=binding.status,
    )

    return {
        **binding_response(binding),
        "rental_id": str(rid),
        "waha_response": join_data,
    }


@router.get("/{rental_id}/binding")
async def get_binding(rental_id: str, db: AsyncSession = Depends(get_db)):
    rid = parse_rental_id(rental_id)
    result = await db.execute(select(RentalInstance).where(RentalInstance.id == rid))
    rental = result.scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    result = await db.execute(select(GroupBinding).where(GroupBinding.rental_id == rid))
    binding = result.scalars().first()
    return {"rental_id": str(rid), **binding_response(binding)}


@router.get("/{rental_id}")
async def get_rental(rental_id: str, db: AsyncSession = Depends(get_db)):
    rid = parse_rental_id(rental_id)
    result = await db.execute(select(RentalInstance).where(RentalInstance.id == rid))
    rental = result.scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    result = await db.execute(
        select(StaffTemplate).where(StaffTemplate.id == rental.template_id)
    )
    template = result.scalars().first()

    return {
        "rental_id": str(rental.id),
        "status": rental.status,
        "staff_name": template.name if template else "Staff AI",
        "staff_emoji": template.avatar_emoji if template else "🤖",
        "staff_specialty": template.specialty if template else None,
        "started_at": rental.started_at,
        "expires_at": rental.expires_at,
    }
