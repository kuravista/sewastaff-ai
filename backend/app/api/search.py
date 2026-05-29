from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis_pool
from app.services.search_cluster_service import process_search

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str


@router.post("")
async def search_roles(payload: SearchRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    session = request.headers.get("x-session-id", "")
    fingerprint = session or ip
    redis = await get_redis_pool()
    return await process_search(payload.query, fingerprint, db, redis)
