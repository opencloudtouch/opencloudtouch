"""Tests for WizardAuditRepository — audit log + config snapshots."""

import pytest
import pytest_asyncio

from opencloudtouch.wizard_audit.repository import WizardAuditRepository


@pytest_asyncio.fixture
async def audit_repo(tmp_path):
    """Create an in-memory-like audit repo using a temp DB file."""
    db_path = str(tmp_path / "test_audit.db")
    repo = WizardAuditRepository(db_path)
    await repo.initialize()
    yield repo
    await repo.close()


@pytest.mark.asyncio
async def test_add_entry(audit_repo: WizardAuditRepository):
    row_id = await audit_repo.add_entry(
        device_id="AA:BB:CC:DD:EE:FF",
        category="user_action",
        event="button_click:next",
        step=3,
        detail='{"target": "next"}',
    )
    assert row_id is not None
    assert row_id > 0


@pytest.mark.asyncio
async def test_get_entries_by_device(audit_repo: WizardAuditRepository):
    await audit_repo.add_entry("dev-1", "nav", "step_enter", step=1)
    await audit_repo.add_entry("dev-2", "nav", "step_enter", step=1)
    await audit_repo.add_entry("dev-1", "nav", "step_complete", step=1)

    entries = await audit_repo.get_entries(device_id="dev-1")
    assert len(entries) == 2
    assert all(e["device_id"] == "dev-1" for e in entries)


@pytest.mark.asyncio
async def test_get_entries_all(audit_repo: WizardAuditRepository):
    await audit_repo.add_entry("dev-1", "nav", "step_enter", step=1)
    await audit_repo.add_entry("dev-2", "nav", "step_enter", step=1)

    entries = await audit_repo.get_entries()
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_add_batch(audit_repo: WizardAuditRepository):
    batch = [
        {"device_id": "dev-1", "category": "nav", "event": f"step_{i}", "step": i}
        for i in range(1, 6)
    ]
    count = await audit_repo.add_batch(batch)
    assert count == 5

    entries = await audit_repo.get_entries(device_id="dev-1")
    assert len(entries) == 5


@pytest.mark.asyncio
async def test_add_config_snapshot(audit_repo: WizardAuditRepository):
    xml_content = "<SoundTouchSdkPrivateCfg><bmxRegistryUrl>http://old</bmxRegistryUrl></SoundTouchSdkPrivateCfg>"
    row_id = await audit_repo.add_config_snapshot(
        device_id="dev-1",
        file_path="/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
        content=xml_content,
        trigger="before_modify_config",
    )
    assert row_id > 0


@pytest.mark.asyncio
async def test_get_config_snapshots(audit_repo: WizardAuditRepository):
    await audit_repo.add_config_snapshot(
        device_id="dev-1",
        file_path="/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
        content="<xml>before</xml>",
        trigger="before_modify_config",
    )
    await audit_repo.add_config_snapshot(
        device_id="dev-1",
        file_path="/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
        content="<xml>after</xml>",
        trigger="after_modify_config",
    )

    snapshots = await audit_repo.get_config_snapshots(device_id="dev-1")
    assert len(snapshots) == 2
    assert snapshots[0]["content"] == "<xml>before</xml>"
    assert snapshots[1]["content"] == "<xml>after</xml>"
    assert snapshots[0]["trigger"] == "before_modify_config"


@pytest.mark.asyncio
async def test_entry_fields(audit_repo: WizardAuditRepository):
    await audit_repo.add_entry(
        device_id="dev-1",
        category="wizard",
        event="wizard_start",
        step=0,
        detail='{"model": "SoundTouch 300"}',
        timestamp="2025-01-15T10:30:00Z",
    )
    entries = await audit_repo.get_entries(device_id="dev-1")
    assert len(entries) == 1
    e = entries[0]
    assert e["device_id"] == "dev-1"
    assert e["category"] == "wizard"
    assert e["event"] == "wizard_start"
    assert e["step"] == 0
    assert "SoundTouch 300" in e["detail"]
    assert e["timestamp"] == "2025-01-15T10:30:00Z"


@pytest.mark.asyncio
async def test_entries_limit(audit_repo: WizardAuditRepository):
    batch = [
        {"device_id": "dev-1", "category": "nav", "event": f"e{i}"} for i in range(20)
    ]
    await audit_repo.add_batch(batch)

    entries = await audit_repo.get_entries(device_id="dev-1", limit=5)
    assert len(entries) == 5
