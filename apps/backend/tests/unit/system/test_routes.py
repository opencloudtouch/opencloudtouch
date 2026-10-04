import pytest
from fastapi import HTTPException

from opencloudtouch.system import routes
from opencloudtouch.system import update_service


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

    assert await routes.update_status() == {
        "phase": "ready"
    }


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
        statuses.append(
            (phase, kwargs)
        )

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

    result = await routes.update()

    assert result == {
        "accepted": True,
        "target_version": "1.5.9",
    }

    assert any(
        phase == "pulling"
        for phase, _ in statuses
    )

    assert statuses[-1][0] == "restarting"


@pytest.mark.asyncio
async def test_update_returns_409_when_active(
    monkeypatch,
):
    monkeypatch.setattr(
        routes,
        "get_update_status",
        lambda: {
            "phase": "restarting"
        },
    )

    with pytest.raises(HTTPException) as exc:
        await routes.update()

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
        await routes.update()

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
        lambda phase, **kwargs: statuses.append(
            (phase, kwargs)
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await routes.update()

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
        await routes.update()

    assert exc.value.status_code == 404
