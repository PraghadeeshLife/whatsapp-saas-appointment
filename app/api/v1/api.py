from fastapi import APIRouter
from app.api.v1.endpoints import webhook, tenants, messages, resources, appointments

api_router = APIRouter()
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
