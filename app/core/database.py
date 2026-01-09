# app/core/database.py

import os
import ssl
from dotenv import load_dotenv
from typing import AsyncGenerator

from loguru import logger
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

# ----------------------------------------------------
# Load environment
# ----------------------------------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set")


# ----------------------------------------------------
# SSL for Supabase Pooler
# ----------------------------------------------------
def make_ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ----------------------------------------------------
# AsyncPG SAFE Config (Supabase PgBouncer)
# ----------------------------------------------------
connect_args = {
    "ssl": make_ssl(),
    "statement_cache_size": 0,  # CRITICAL: Disable prepared statements for PgBouncer
}

logger.info("🔄 Configuring Database (Pooler Mode)")


# ----------------------------------------------------
# Engine (NO SQLAlchemy pooling)
# ----------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
    poolclass=NullPool,  # Supabase PgBouncer handles pooling
)


# ----------------------------------------------------
# Sessions
# ----------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ----------------------------------------------------
# Create tables (DEV / TEST ONLY)
# ----------------------------------------------------
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# ----------------------------------------------------
# Test Connection (Silent, Safe for Metrics)
# ----------------------------------------------------
async def test_connection():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        logger.debug("DB connection OK (Pooler)")
