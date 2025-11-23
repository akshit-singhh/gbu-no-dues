# app/core/database.py

import os
import ssl
from uuid import uuid4  # <--- NEW IMPORT
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlmodel import SQLModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 1. Load Environment
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set.")

# 2. SSL Context (Optimized for Supabase Pooler)
def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# 3. Engine Configuration
connect_args = {
    "ssl": _make_ssl_context(),
    
    # ---------------------------------------------------------
    # THE FINAL FIX
    # ---------------------------------------------------------
    # 1. We still try to disable the cache.
    "statement_cache_size": 0,
    
    # 2. SECURITY NET: If cache disable fails (which it is doing),
    # we force every statement to have a unique random name.
    # This prevents "prepared statement already exists" errors 
    # when Supabase reuses connections.
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    # ---------------------------------------------------------
    
    "server_settings": {
        "jit": "off"
    }
}

print(f"🔄 Configuring Database")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True 
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# 4. Dependencies
from app.models.department import Department
from app.models.user import User
from app.models.student import Student
from app.models.application import Application

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# Deprecated for Transaction Mode (Do not use)
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def test_connection() -> None:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("✅ Successfully connected to database (Transaction Mode).")
    except Exception as e:
        print("❌ Database connection failed:")
        print(f" → {e}")