from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import sys
import time
import uuid
import os
import socket
import redis.asyncio as redis

# Database & Seeding
from app.core.database import test_connection, init_db
from app.core.seeding_logic import seed_all

# Rate Limiting
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limiter import limiter

# Config
from app.core.config import settings

# Routers (Import common last to avoid circular issues)
from app.api.endpoints import (
    auth as auth_router,
    users as users_router,
    account as account_router,
    applications as applications_router,
    students as students_router,
    auth_student as auth_student_router,
    approvals as approvals_router,
    verification as verification_router,
    utils as utils_router,
    jobs as jobs_router,
    common as common_router
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

    try:
        # 1. DATABASE CHECK
        await test_connection()
        logger.success("✅ Database connection established.")
        
        # 2. REDIS CHECK
        if settings.REDIS_URL:
            try:
                # Test connection with a Ping
                r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
                await r.ping()
                # Log success but mask the full URL password for security
                host = settings.REDIS_URL.split("@")[-1]
                logger.success(f"✅ Redis Connected: {host}")
                await r.close()
            except Exception as e:
                logger.error(f"❌ Redis Connection Failed: {e}")
        else:
            logger.warning("⚠️ No REDIS_URL found. Rate limiting is running in Memory (NOT Production Ready).")

        # 3. DB INIT & SEEDING (Code-First Approach)
        await init_db()
        await seed_all() # Runs Schools, Depts, Linking, and Admin creation
        
    except Exception as e:
        logger.error(f"⚠️ Startup sequence partial failure: {e}")

    yield
    logger.warning("🛑 Backend shutting down...")

# ------------------------------------------------------------
# FASTAPI APP INIT
# ------------------------------------------------------------
app = FastAPI(
    title="GBU No Dues Backend",
    version="1.6.0",
    description="Backend service for the GBU No Dues Management System.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    logger.bind(request_id=request_id).info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

@app.middleware("http")
async def traffic_stats_middleware(request: Request, call_next):
    # Skip tracking for internal routes or static files to save DB writes
    if not request.url.path.startswith(("/static", "/favicon.ico", "/docs", "/openapi.json")):
        try:
            if settings.REDIS_URL:
                # Fire and forget - don't await the connection setup too long
                r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
                # Key Format: TRAFFIC:GET:/api/users
                key = f"TRAFFIC:{request.method}:{request.url.path}"
                await r.incr(key)
                await r.close()
        except Exception:
            # Never fail the request just because stats logging failed
            pass
            
    response = await call_next(request)
    return response

# ------------------------------------------------------------
# STATIC FILES (Vercel Friendly)
# ------------------------------------------------------------
# We wrap path creation in try/except because Vercel is Read-Only
try:
    if not os.path.exists("app/static/certificates"):
        os.makedirs("app/static/certificates", exist_ok=True)
except Exception:
    pass

if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ------------------------------------------------------------
# METRICS API
# ------------------------------------------------------------
@app.get("/api/metrics", tags=["System"])
async def metrics():
    uptime_seconds = int(time.time() - START_TIME)
    
    db_status = "Disconnected"
    try:
        await test_connection()
        db_status = "Connected"
    except Exception:
        db_status = "Error"

    smtp_status = "Not Configured"
    if settings.SMTP_HOST:
        try:
            sock = socket.create_connection((settings.SMTP_HOST, settings.SMTP_PORT), timeout=2)
            sock.close()
            smtp_status = "Connected"
        except Exception:
            smtp_status = "Error"

    return {
        "status": "Online",
        "version": app.version,
        "uptime": uptime_seconds,
        "database": db_status,
        "smtp_server": smtp_status,
        "environment": "Serverless (Vercel)" if os.environ.get("VERCEL") else "Development"
    }

# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
# Use settings.FRONTEND_URLS split by comma
frontend_origins = [url.strip() for url in settings.FRONTEND_URLS.split(",")] if settings.FRONTEND_URLS else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=settings.FRONTEND_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
# app.include_router(captcha_router.router) # ❌ Removed: No longer needed
app.include_router(utils_router.router)
app.include_router(jobs_router.router)
app.include_router(common_router.router)

@app.get("/", tags=["System"])
async def root():
    return {"status": "ok", "message": "Backend running successfully 🚀"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav_path = "app/static/favicon.ico"
    return FileResponse(fav_path) if os.path.exists(fav_path) else JSONResponse({"detail": "No favicon"}, status_code=404)