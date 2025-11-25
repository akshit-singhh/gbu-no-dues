import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# ------------------------------------------------------------------
# FORCE TESTING MODE
# This must be done BEFORE importing app.main to ensure database.py
# sees the variable and uses NullPool.
# ------------------------------------------------------------------
os.environ["TESTING"] = "true"

from app.main import app

@pytest_asyncio.fixture
async def client():
    """
    Correct fixture for httpx >= 0.27
    Uses ASGITransport() instead of app=...
    """
    # The app dependency is imported after setting the env var,
    # so the DB engine should now initialize with NullPool.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac