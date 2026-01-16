# app/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import sys
import time
import psutil
import uuid
import os
import socket

# Rate Limiting Imports
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limiter import limiter  # <--- IMPORT LIMITER

# Core modules
from app.core.database import test_connection, init_db, AsyncSessionLocal
from app.core.config import settings
from app.services.auth_service import get_user_by_email, create_user
from app.models.user import UserRole
from app.api.endpoints import utils

# Routers
from app.api.endpoints import (
    auth as auth_router,
    users as users_router,
    account as account_router,
    applications as applications_router,
    students as students_router,
    auth_student as auth_student_router,
    approvals as approvals_router,
    verification as verification_router,
    captcha as captcha_router,
)

# ------------------------------------------------------------
# LOGURU CONFIGURATION
# ------------------------------------------------------------
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# ------------------------------------------------------------
# GLOBAL METRICS
# ------------------------------------------------------------
START_TIME = time.time()

# ------------------------------------------------------------
# LIFESPAN (Startup / Shutdown)
# ------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting GBU No Dues Backend...")

    # 1. Database check
    try:
        await test_connection()
        logger.success("Database connection established.")
        await init_db()
        logger.success("Database tables ready.")
    except Exception:
        logger.exception("❌ Startup failed: Database unavailable.")
        raise

    # 2. Seed Super Admin
    try:
        async with AsyncSessionLocal() as session:
            if settings.SUPER_ADMIN_EMAIL and settings.SUPER_ADMIN_PASSWORD:
                existing = await get_user_by_email(session, settings.SUPER_ADMIN_EMAIL)
                if not existing:
                    logger.info("Seeding Super Admin account...")
                    await create_user(
                        session=session,
                        name=settings.SUPER_ADMIN_NAME or "Super Admin",
                        email=settings.SUPER_ADMIN_EMAIL,
                        password=settings.SUPER_ADMIN_PASSWORD,
                        role=UserRole.Admin,
                    )
                    logger.success("Super Admin created.")
                else:
                    logger.info("Super Admin already exists.")
            else:
                logger.warning("Super Admin credentials missing.")
    except Exception:
        logger.exception("Super Admin seeding failed.")

    logger.success("✅ Backend startup completed.")
    yield
    logger.warning("🛑 Backend shutting down...")

# ------------------------------------------------------------
# FASTAPI APP INIT
# ------------------------------------------------------------
app = FastAPI(
    title="GBU No Dues Backend",
    version="1.4.0",
    description="Backend service for the GBU No Dues Management System.",
    lifespan=lifespan,
)

# ------------------------------------------------------------
# RATE LIMITER CONFIGURATION
# ------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ------------------------------------------------------------
# REQUEST ID MIDDLEWARE
# ------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    logger.bind(request_id=request_id).info(
        f"{request.method} {request.url.path}"
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# ------------------------------------------------------------
# GLOBAL EXCEPTION HANDLER
# ------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )

# ------------------------------------------------------------
# STATIC FILES & FAVICON
# ------------------------------------------------------------
os.makedirs("app/static", exist_ok=True)
os.makedirs("app/static/certificates", exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    if os.path.exists("app/static/favicon.ico"):
        return FileResponse("app/static/favicon.ico")
    return JSONResponse({"detail": "No favicon"}, status_code=404)

@app.get("/status", include_in_schema=False)
async def status_page():
    if os.path.exists("app/static/status.html"):
        return FileResponse("app/static/status.html")
    return JSONResponse({"status": "running"}, status_code=200)

# ------------------------------------------------------------
# METRICS API
# ------------------------------------------------------------
@app.get("/api/metrics", tags=["System"])
async def metrics():
    uptime_seconds = int(time.time() - START_TIME)
    cpu_usage = psutil.cpu_percent(interval=None)
    ram_usage = psutil.virtual_memory().percent

    try:
        disk_usage = psutil.disk_usage("/").percent
    except Exception:
        disk_usage = 0

    # 1. Database Check
    db_latency = 0
    db_status = "Disconnected"
    try:
        start = time.time()
        await test_connection()
        db_latency = round((time.time() - start) * 1000, 2)
        db_status = "Connected"
    except Exception:
        db_status = "Error"

    # 2. SMTP Server Check
    smtp_status = "Disconnected"
    try:
        if settings.SMTP_HOST:
            # Try to connect to the SMTP port (timeout 2s)
            sock = socket.create_connection((settings.SMTP_HOST, settings.SMTP_PORT), timeout=2)
            sock.close()
            smtp_status = "Connected"
        else:
            smtp_status = "Not Configured"
    except Exception:
        smtp_status = "Error"

    return {
        "status": "Online",
        "version": app.version,
        "uptime": uptime_seconds,
        "cpu": cpu_usage,
        "ram": ram_usage,
        "disk": disk_usage,
        "database": db_status,
        "db_latency_ms": db_latency,
        "smtp_server": smtp_status,
        "db_pool": "Managed by Supabase PgBouncer",
    }

# ------------------------------------------------------------
# CORS CONFIGURATION
# ------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware
frontend_origins = [url.strip() for url in settings.FRONTEND_URLS.split(",")]

#  Regex for dynamic domains from .env
frontend_regex = settings.FRONTEND_REGEX or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,       # Exact URLs
    allow_origin_regex=frontend_regex,    # Dynamic subdomains
    allow_credentials=True,               # Needed for cookies/auth headers
    allow_methods=["*"],                  # All HTTP methods
    allow_headers=["*"],                  # All headers
)


# ------------------------------------------------------------
# ROUTERS
# ------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(account_router.router)
app.include_router(students_router.router)
app.include_router(auth_student_router.router)
app.include_router(applications_router.router)
app.include_router(approvals_router.router)
app.include_router(verification_router.router)
app.include_router(captcha_router.router)
app.include_router(utils.router)

# ------------------------------------------------------------
# ROOT HEALTH CHECK
# ------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {
        "status": "ok",
        "service": "GBU No Dues Backend",
        "version": app.version,
        "message": "Backend running successfully 🚀",
        "dashboard_url": "/status",
    }