from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from opencloudtouch.system import routes, update_service


def update_request(version="1.5.9"):
    return routes.UpdateRequest(target_version=version)


def test_update_requires_json_confirmation_body():
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    response = client.post("/api/system/update")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_check_update(monkeypatch):
    async def fake_check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "release_url": "https://example.test",
        }

    monkeypatch.setattr(
        routes,
        "check_for_update",
        fake_check,
    )

    result = await routes.check_update()

    assert result["update_available"] is True


@pytest.mark.asyncio
async def test_update_status(monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {"phase": "ready"},
    )

    assert await routes.update_status() == {"phase": "ready"}


@pytest.mark.asyncio
async def test_update_uses_target_release(
    monkeypatch,
):
    statuses = []

    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {"phase": "idle"},
    )

    async def fake_check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "release_url": "https://example.test",
        }

    async def fake_container():
        return {"Id": "oct123"}

    async def fake_pull(
        image,
        callback,
    ):
        assert image.endswith(":1.5.9")
        callback(
            50,
            "Pulling new image...",
        )

    async def fake_helper(
        container_id,
        image,
    ):
        assert container_id == "oct123"
        assert image.endswith(":1.5.9")
        return "helper123"

    def fake_status(phase, **kwargs):
        statuses.append((phase, kwargs))

    monkeypatch.setattr(
        routes,
        "check_for_update",
        fake_check,
    )
    monkeypatch.setattr(
        routes,
        "get_oct_container",
        fake_container,
    )
    monkeypatch.setattr(
        routes,
        "pull_oct_image",
        fake_pull,
    )
    monkeypatch.setattr(
        routes,
        "launch_update_helper",
        fake_helper,
    )
    monkeypatch.setattr(
        routes,
        "set_update_status",
        fake_status,
    )

    result = await routes.update(update_request())

    assert result == {
        "accepted": True,
        "target_version": "1.5.9",
    }

    assert any(phase == "pulling" for phase, _ in statuses)

    assert statuses[-1][0] == "restarting"


@pytest.mark.asyncio
async def test_update_returns_409_when_active(
    monkeypatch,
):
    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {
            "phase": "restarting",
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request())

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_returns_409_when_none_available(
    monkeypatch,
):
    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {"phase": "idle"},
    )

    async def fake_check():
        return {
            "current": "1.5.8",
            "latest": "1.5.8",
            "update_available": False,
            "release_url": "https://example.test",
        }

    monkeypatch.setattr(
        routes,
        "check_for_update",
        fake_check,
    )

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request("1.5.8"))

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_docker_failure_returns_503(monkeypatch):
    statuses = []

    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {"phase": "idle"},
    )

    async def check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "release_url": "https://example.test",
        }

    async def fail():
        raise RuntimeError("Docker unavailable")

    monkeypatch.setattr(routes, "check_for_update", check)
    monkeypatch.setattr(routes, "get_oct_container", fail)

    monkeypatch.setattr(
        routes,
        "set_update_status",
        lambda phase, **kwargs: statuses.append((phase, kwargs)),
    )

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request())

    assert exc.value.status_code == 503
    assert statuses[-1][0] == "failed"
    assert statuses[-1][1]["error"] == "Docker unavailable"


@pytest.mark.asyncio
async def test_check_update_maps_release_failure_to_503(monkeypatch):
    async def fail():
        raise update_service.UpdateCheckError("GitHub unavailable")

    monkeypatch.setattr(routes, "check_for_update", fail)

    with pytest.raises(HTTPException) as exc:
        await routes.check_update()

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_update_returns_404_without_container(monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {"phase": "idle"},
    )

    async def check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "release_url": "https://example.test",
        }

    async def no_container():
        return None

    monkeypatch.setattr(routes, "check_for_update", check)
    monkeypatch.setattr(routes, "get_oct_container", no_container)

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_allows_stale_active_status(monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {"phase": "pulling", "updated_at": "2020-01-01T00:00:00Z"},
    )

    async def check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "release_url": "https://example.test",
        }

    async def container():
        return {"Id": "oct123"}

    async def pull(image, callback):
        return None

    async def helper(container_id, image):
        return "helper123"

    monkeypatch.setattr(routes, "check_for_update", check)
    monkeypatch.setattr(routes, "get_oct_container", container)
    monkeypatch.setattr(routes, "pull_oct_image", pull)
    monkeypatch.setattr(routes, "launch_update_helper", helper)
    monkeypatch.setattr(routes, "set_update_status", lambda *args, **kwargs: None)

    result = await routes.update(update_request())

    assert result["accepted"] is True


@pytest.mark.asyncio
async def test_update_rejects_target_version_mismatch(monkeypatch):
    monkeypatch.setattr(routes, "get_update_status", lambda: {"phase": "idle"})

    async def check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "release_url": "https://example.test",
        }

    monkeypatch.setattr(routes, "check_for_update", check)

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request("1.5.10"))

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_disabled_returns_503_without_docker_calls(monkeypatch):
    monkeypatch.setattr(routes, "get_update_status", lambda: {"phase": "idle"})

    async def check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "self_update_enabled": False,
            "self_update_reason": "Docker socket is not mounted",
        }

    async def unexpected_container():
        pytest.fail("Docker must not be contacted when self-update is disabled")

    monkeypatch.setattr(routes, "check_for_update", check)
    monkeypatch.setattr(routes, "get_oct_container", unexpected_container)

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request())

    assert exc.value.status_code == 503
    assert exc.value.detail == "Docker socket is not mounted"


@pytest.mark.asyncio
async def test_update_status_write_failure_keeps_original_503(monkeypatch):
    monkeypatch.setattr(routes, "get_update_status", lambda: {"phase": "idle"})

    async def check():
        return {
            "current": "1.5.8",
            "latest": "1.5.9",
            "update_available": True,
            "self_update_enabled": True,
        }

    async def fail():
        raise RuntimeError("Docker unavailable")

    def fail_status(*args, **kwargs):
        raise OSError("status file is read-only")

    monkeypatch.setattr(routes, "check_for_update", check)
    monkeypatch.setattr(routes, "get_oct_container", fail)
    monkeypatch.setattr(routes, "set_update_status", fail_status)

    with pytest.raises(HTTPException) as exc:
        await routes.update(update_request())

    assert exc.value.status_code == 503
    assert exc.value.detail == "Docker unavailable"
