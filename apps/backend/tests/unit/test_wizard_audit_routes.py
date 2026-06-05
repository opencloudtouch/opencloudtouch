"""Tests for wizard audit log API routes."""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from opencloudtouch.wizard_audit.repository import WizardAuditRepository
from opencloudtouch.wizard_audit.routes import audit_router


@pytest_asyncio.fixture
async def app_with_audit(tmp_path):
    """Create a minimal FastAPI app with wizard audit routes."""
    app = FastAPI()
    app.include_router(audit_router)

    repo = WizardAuditRepository(str(tmp_path / "test.db"))
    await repo.initialize()
    app.state.wizard_audit_repo = repo

    yield app
    await repo.close()


@pytest_asyncio.fixture
async def client(app_with_audit):
    transport = ASGITransport(app=app_with_audit)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_post_audit_entry(client: AsyncClient):
    resp = await client.post(
        "/api/wizard/audit-log",
        json={
            "device_id": "dev-1",
            "category": "user_action",
            "event": "button_click:next",
            "step": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_post_audit_entry_with_detail(client: AsyncClient):
    resp = await client.post(
        "/api/wizard/audit-log",
        json={
            "device_id": "dev-1",
            "category": "dropdown",
            "event": "platform_change",
            "step": 1,
            "detail": '{"value": "windows"}',
            "timestamp": "2025-01-15T10:30:00Z",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_post_audit_batch(client: AsyncClient):
    entries = [
        {"device_id": "dev-1", "category": "nav", "event": f"step_{i}", "step": i}
        for i in range(1, 6)
    ]
    resp = await client.post(
        "/api/wizard/audit-log/batch",
        json={"entries": entries},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["count"] == 5


@pytest.mark.asyncio
async def test_post_audit_batch_too_many(client: AsyncClient):
    entries = [
        {"device_id": "dev-1", "category": "nav", "event": f"e{i}"} for i in range(201)
    ]
    resp = await client.post(
        "/api/wizard/audit-log/batch",
        json={"entries": entries},
    )
    assert resp.status_code == 422  # Validation error (max 200)


@pytest.mark.asyncio
async def test_post_config_snapshot(client: AsyncClient):
    resp = await client.post(
        "/api/wizard/config-snapshot",
        json={
            "device_id": "dev-1",
            "file_path": "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
            "content": "<xml>test</xml>",
            "trigger": "before_modify_config",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_audit_entry_missing_required_fields(client: AsyncClient):
    resp = await client.post(
        "/api/wizard/audit-log",
        json={"device_id": "dev-1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_audit_entry_invalid_step(client: AsyncClient):
    resp = await client.post(
        "/api/wizard/audit-log",
        json={
            "device_id": "dev-1",
            "category": "nav",
            "event": "test",
            "step": 99,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_no_repo_returns_503():
    """When wizard_audit_repo is not set, endpoints return 503."""
    app = FastAPI()
    app.include_router(audit_router)
    # No repo set on app.state

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/wizard/audit-log",
            json={"device_id": "d", "category": "c", "event": "e"},
        )
    assert resp.status_code == 503
