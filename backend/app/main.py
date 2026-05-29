from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db, create_all_tables, SessionLocal
from app.core.redis import get_redis_pool
from app.core.logging import configure_logging, get_logger
from app.core import database as db_module
from app.core import redis as redis_module
from app.models import StaffTemplate

from app.api.staff import router as staff_router
from app.api.onboarding import router as onboarding_router
from app.api.trial import router as trial_router
from app.api.webhooks_waha import router as webhooks_router
from app.api.admin import router as admin_router
from app.api.rental import router as rental_router
from app.api.search import router as search_router

import app.models.staff_memory
import app.models.search_cluster
import app.models.search_query
import app.models.knowledge_item
import app.models.rental_instance
import app.models.tenant
import app.models.group_binding
import app.models.message_event
import app.models.staff_template


logger = get_logger(__name__)

TEMPLATES_SEED = [
    dict(slug="hr", name="Mbak Sera", specialty="HR & Rekrutmen", avatar_emoji="👩‍💼", price_monthly_idr=99000, base_prompt="", is_active=True),
    dict(slug="pa", name="Mas Dika", specialty="Personal Assistant", avatar_emoji="🗂️", price_monthly_idr=79000, base_prompt="", is_active=True),
    dict(slug="akuntansi", name="Mbak Rini", specialty="Keuangan & Akuntansi", avatar_emoji="📊", price_monthly_idr=99000, base_prompt="", is_active=True),
    dict(slug="cs", name="Kak Aldi", specialty="Customer Service", avatar_emoji="💬", price_monthly_idr=79000, base_prompt="", is_active=True),
    dict(slug="sales", name="Mas Rio", specialty="Sales Follow-up", avatar_emoji="🎯", price_monthly_idr=99000, base_prompt="", is_active=True),
]


async def seed_staff_templates_if_empty():
    async with SessionLocal() as db:
        result = await db.execute(select(StaffTemplate))
        existing = result.scalars().all()
        if len(existing) == 0:
            for t in TEMPLATES_SEED:
                db.add(StaffTemplate(**t))
            await db.commit()
            logger.info("staff_templates_seeded")


async def db_health_check() -> bool:
    return await db_module.health_check()


async def redis_health_check() -> bool:
    return await redis_module.health_check()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await get_redis_pool()
    await create_all_tables()
    await seed_staff_templates_if_empty()
    yield


app = FastAPI(title="SewaStaff AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(staff_router)
app.include_router(onboarding_router)
app.include_router(trial_router)
app.include_router(webhooks_router)
app.include_router(admin_router)
app.include_router(rental_router)
app.include_router(search_router)


@app.get("/api/health")
async def health():
    db_ok = await db_health_check()
    redis_ok = await redis_health_check()
    return {
        "status": "ok",
        "version": "0.1.0",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }


@app.get("/api/ready")
async def ready():
    from fastapi import Response
    db_ok = await db_health_check()
    redis_ok = await redis_health_check()
    if not db_ok or not redis_ok:
        return Response(status_code=503, content="not ready")
    return {"status": "ready"}
