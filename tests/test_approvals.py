import pytest

@pytest.mark.asyncio
async def test_approvals_list_all_route(client):
    # GET /api/approvals/all
    res = await client.get("/api/approvals/all")
    assert res.status_code in (200, 401, 403)

@pytest.mark.asyncio
async def test_get_approval_detail_route(client):
    # GET /api/approvals/{app_id}
    # Use a fake UUID; the route should exist and probably return 404 or 200
    res = await client.get("/api/approvals/00000000-0000-0000-0000-000000000000")
    assert res.status_code in (200, 401, 403, 404)
