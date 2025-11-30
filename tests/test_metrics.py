import pytest

@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    res = await client.get("/api/metrics")
    assert res.status_code == 200
    
    data = res.json()
    
    # Check structure
    assert data["status"] == "Online"
    assert "cpu" in data
    assert "ram" in data
    assert "database" in data
    
    # Check data types
    assert isinstance(data["uptime"], int)
    assert isinstance(data["version"], str)