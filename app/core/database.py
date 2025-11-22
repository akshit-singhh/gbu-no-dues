# app/core/database.py
import ssl
import os
import logging
from typing import AsyncGenerator

from sqlmodel import SQLModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings

logger = logging.getLogger("uvicorn")

# ------------------------------------------------------------
# SSL handling for production
# ------------------------------------------------------------
connect_args = {}

if settings.ENV == "prod":
    if settings.DB_SSL_VERIFY:
        # Path to custom CA certificate
        cafile_path = os.path.join(os.path.dirname(__file__), "..", "..", "certs", "prod-ca-2021.crt")
        cafile_path = os.path.abspath(cafile_path)
        if not os.path.exists(cafile_path):
            logger.error("❌ CA certificate not found at: %s", cafile_path)
            raise FileNotFoundError(f"CA certificate not found at: {cafile_path}")

        ssl_context = ssl.create_default_context(cafile=cafile_path)
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        connect_args = {"ssl": ssl_context}
        logger.info("🔒 Using SSL with custom CA certificate at %s", cafile_path)
    else:
        connect_args = {"ssl": False}  # insecure for dev/testing
        logger.warning("⚠️ DB_SSL_VERIFY is False. SSL verification disabled!")
else:
    connect_args = {"ssl": False}  # local/dev mode
    logger.info("⚠️ Running in development mode. SSL disabled.")

# ------------------------------------------------------------
# Async Engine
# ------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# ------------------------------------------------------------
# Import all models
# ------------------------------------------------------------
from app.models.department import Department
from app.models.user import User
from app.models.student import Student
from app.models.application import Application

# ------------------------------------------------------------
# FastAPI Dependency
# ------------------------------------------------------------
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# ------------------------------------------------------------
# Create tables (development only)
# ------------------------------------------------------------
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("✅ Database tables created (development only).")

# ------------------------------------------------------------
# Test connection
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
