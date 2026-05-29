from fastapi import APIRouter
from app.api import webhooks_waha, staff, onboarding, trial, admin, rental

api_router = APIRouter()

api_router.include_router(webhooks_waha.router)
api_router.include_router(staff.router)
api_router.include_router(onboarding.router)
api_router.include_router(trial.router)
api_router.include_router(admin.router)
api_router.include_router(rental.router)
