from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from contextlib import asynccontextmanager
import newrelic.agent

# Setup logging immediately
setup_logging()

# Initialize New Relic Agent if config exists (though generally handled by newrelic-admin)
if settings.new_relic_license_key:
    print(f"KEYYYY: {settings.new_relic_license_key}")
    try:
        newrelic.agent.initialize()
    except Exception:
        pass # Expected if already initialized via admin script

import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Potential startup logic
    yield
    # Potential shutdown logic

app = FastAPI(
    title=settings.app_name,
    openapi_url=f"{settings.api_v1_str}/openapi.json",
    lifespan=lifespan
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    logger.info(f"path={request.url.path} method={request.method} status={response.status_code} duration={formatted_process_time}ms")
    return response

# Set all CORS enabled origins
if settings.backend_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.backend_cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.api_v1_str)

@app.get("/")
async def root():
    return {"message": "WhatsApp Appointment SaaS Backend is running"}
