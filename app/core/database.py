# app/core/database.py

import ssl
import logging
from typing import AsyncGenerator

from sqlmodel import SQLModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings

# ------------------------------------------------------------
# Logger setup
# ------------------------------------------------------------
logger = logging.getLogger("uvicorn")  # integrates with FastAPI/Uvicorn logs

# ------------------------------------------------------------
# SSL Setup
# ------------------------------------------------------------
def _make_ssl_context() -> ssl.SSLContext:
    """
    Creates SSL context based on environment and settings.
    - In dev, SSL verification is disabled by default.
    - In production, SSL verification is enabled.
    """
    ctx = ssl.create_default_context()
    # Safe fallback: ensure DB_SSL_VERIFY is a bool
    ssl_verify = bool(getattr(settings, "DB_SSL_VERIFY", True))

    # If in development, optionally override SSL verification
    if getattr(settings, "ENV", "development") == "development":
        ssl_verify = False

    if not ssl_verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        logger.warning("⚠️ SSL verification is DISABLED (dev mode).")
    else:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

    return ctx

# ------------------------------------------------------------
# Engine Config
# ------------------------------------------------------------
_connect_args = {"ssl": _make_ssl_context()}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# ------------------------------------------------------------
# Import all models (important for metadata)
# ------------------------------------------------------------
from app.models.department import Department
from app.models.user import User
from app.models.student import Student
from app.models.application import Application
# Add other models if needed:
# from app.models.application_stage import ApplicationStage
# from app.models.audit_log import AuditLog
# from app.models.certificate import Certificate

# ------------------------------------------------------------
# Dependency for FastAPI routes
# ------------------------------------------------------------
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# ------------------------------------------------------------
# Create all tables (development only)
# ------------------------------------------------------------
async def init_db() -> None:
    """
    Creates all tables declared via SQLModel.
    WARNING: Do NOT use in production. Use Alembic for migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("✅ Database tables created (development only).")

# ------------------------------------------------------------
# Test DB Connection (Startup)
# ------------------------------------------------------------
async def test_connection() -> None:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("✅ Successfully connected to database.")
    except Exception as e:
        logger.error("❌ Database connection failed:")
        logger.error(" → %s", e)
        raise e
