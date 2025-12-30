from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    openapi_url=f"{settings.api_v1_str}/openapi.json"
)

app.include_router(api_router, prefix=settings.api_v1_str)

@app.get("/")
async def root():
    return {"message": "WhatsApp Appointment SaaS Backend is running"}
