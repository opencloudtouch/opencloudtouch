import json
import sys

import pytest

from opencloudtouch.system import update_helper


class FakeResponse:
    def __init__(
        self,
        data=None,
        status_code=200,
    ):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class FakeClient:
    def __init__(self, inspect):
        self.inspect = inspect

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    async def get(self, path):
        assert path == (
            "/containers/old123/json"
        )
        return FakeResponse(self.inspect)


def old_inspect():
    return {
        "Name": "/opencloudtouch",
        "Image": "sha256:oldimage",
        "State": {
            "Running": True,
        },
        "Config": {
            "Image": (
                "ghcr.io/opencloudtouch/"
                "opencloudtouch:1.5.8"
            ),
            "Env": [
                "OCT_PORT=7777",
                "OCT_VERSION=1.5.8",
                "OCT_BUILD_SIGNATURE=test",
                "PATH=/usr/local/bin",
            ],
            "Cmd": None,
            "Entrypoint": ["/entrypoint.sh"],
            "WorkingDir": "/app",
            "ExposedPorts": None,
            "Healthcheck": {
                "Test": [
                    "CMD",
                    "/entrypoint.sh",
                    "health",
                ],
            },
            "Labels": {
                "com.docker.compose.project": "oct",
                "com.docker.compose.service": "opencloudtouch",
                "com.docker.compose.image": "sha256:stale",
                "com.docker.compose.config-hash": "stale",
              "org.opencontainers.image.version": "1.5.8",
            },
        },
        "HostConfig": {
            "NetworkMode": "host",
            "Binds": [
                "oct-data:/data:rw",
                (
                    "/var/run/docker.sock:"
                    "/var/run/docker.sock:rw"
                ),
            ],
            "RestartPolicy": {
                "Name": "unless-stopped",
                "MaximumRetryCount": 0,
            },
            "LogConfig": {},
            "ShmSize": 67108864,
            "PortBindings": {"7777/tcp": [{"HostPort": "7777"}]},
            "PublishAllPorts": False,
        },
    }


def test_build_container_config_filters_metadata():
    config = (
        update_helper.build_container_config(
            old_inspect()
        )
    )

    assert "OCT_PORT=7777" in config["Env"]

    assert not any(
        value.startswith("OCT_VERSION=")
        for value in config["Env"]
    )

    assert not any(
        value.startswith(
            "OCT_BUILD_SIGNATURE="
        )
        for value in config["Env"]
    )

    assert "Entrypoint" not in config
    assert "Cmd" not in config
    assert "WorkingDir" not in config
    assert config["Healthcheck"] == old_inspect()["Config"]["Healthcheck"]

    assert config["HostConfig"]["PortBindings"] == {"7777/tcp": [{"HostPort": "7777"}]}
    assert config["HostConfig"]["PublishAllPorts"] is False

    assert config["Labels"] == {
        "com.docker.compose.project": "oct",
        "com.docker.compose.service": "opencloudtouch",
    }


@pytest.mark.asyncio
async def test_successful_update_uses_target_image(
    tmp_path,
    monkeypatch,
):
    client = FakeClient(old_inspect())

    monkeypatch.setattr(
        update_helper.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "update_helper",
            "old123",
            (
                "ghcr.io/opencloudtouch/"
                "opencloudtouch:1.5.9"
            ),
        ],
    )

    monkeypatch.setattr(
        update_helper,
        "STATUS_PATH",
        tmp_path / "update-status.json",
    )

    update_helper.STATUS_PATH.write_text(
        json.dumps(
            {
                "phase": "restarting",
                "current_version": "1.5.8",
                "target_version": "1.5.9",
            }
        ),
        encoding="utf-8",
    )

    created = []

    async def fake_remove(
        client,
        container_id,
    ):
        pass

    async def fake_create(
        client,
        name,
        config,
    ):
        created.append(config)
        return "new123"

    async def fake_wait(
        client,
        container_id,
        attempts=45,
    ):
        pass

    monkeypatch.setattr(
        update_helper,
        "remove_container",
        fake_remove,
    )
    monkeypatch.setattr(
        update_helper,
        "create_and_start",
        fake_create,
    )
    monkeypatch.setattr(
        update_helper,
        "wait_for_health",
        fake_wait,
    )

    await update_helper.main()

    assert created[0]["Image"] == (
        "ghcr.io/opencloudtouch/"
        "opencloudtouch:1.5.9"
    )

    status = json.loads(
        update_helper.STATUS_PATH.read_text()
    )

    assert status["phase"] == "ready"
    assert status["progress_pct"] == 100
    assert status["current_version"] == "1.5.9"


@pytest.mark.asyncio
async def test_failed_update_rolls_back_to_sha(
    tmp_path,
    monkeypatch,
):
    client = FakeClient(old_inspect())

    monkeypatch.setattr(
        update_helper.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "update_helper",
            "old123",
            (
                "ghcr.io/opencloudtouch/"
                "opencloudtouch:1.5.9"
            ),
        ],
    )

    monkeypatch.setattr(
        update_helper,
        "STATUS_PATH",
        tmp_path / "update-status.json",
    )

    update_helper.STATUS_PATH.write_text(
        json.dumps(
            {
                "phase": "restarting",
                "current_version": "1.5.8",
                "target_version": "1.5.9",
            }
        ),
        encoding="utf-8",
    )

    removed = []
    created = []

    async def fake_remove(
        client,
        container_id,
    ):
        removed.append(container_id)

    async def fake_create(
        client,
        name,
        config,
    ):
        created.append(config)

        if len(created) == 1:
            return "broken123"

        return "rollback123"

    async def fake_wait(
        client,
        container_id,
        attempts=45,
    ):
        if container_id == "broken123":
            raise RuntimeError(
                "Updated container became unhealthy"
            )

    monkeypatch.setattr(
        update_helper,
        "remove_container",
        fake_remove,
    )
    monkeypatch.setattr(
        update_helper,
        "create_and_start",
        fake_create,
    )
    monkeypatch.setattr(
        update_helper,
        "wait_for_health",
        fake_wait,
    )

    with pytest.raises(SystemExit):
        await update_helper.main()

    assert created[0]["Image"] == (
        "ghcr.io/opencloudtouch/"
        "opencloudtouch:1.5.9"
    )
    assert created[1]["Image"] == (
        "sha256:oldimage"
    )

    status = json.loads(
        update_helper.STATUS_PATH.read_text()
    )

    assert status["phase"] == "rolled_back"
    assert status["current_version"] == "1.5.8"


class HealthClient:
    def __init__(self, states):
        self.states = iter(states)

    async def get(self, path):
        return FakeResponse({"State": next(self.states)})

@pytest.mark.asyncio
async def test_wait_for_health_accepts_healthy(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(update_helper.asyncio, "sleep", no_sleep)

    client = HealthClient(
        [{"Running": True, "Health": {"Status": "healthy"}}]
    )

    await update_helper.wait_for_health(client, "abc", attempts=1)

@pytest.mark.asyncio
async def test_wait_for_health_rejects_stopped_container(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(update_helper.asyncio, "sleep", no_sleep)

    client = HealthClient([{"Running": False}])

    with pytest.raises(RuntimeError, match="stopped unexpectedly"):
        await update_helper.wait_for_health(client, "abc", attempts=1)

@pytest.mark.asyncio
async def test_wait_for_health_rejects_unhealthy(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(update_helper.asyncio, "sleep", no_sleep)

    client = HealthClient(
        [{"Running": True, "Health": {"Status": "unhealthy"}}]
    )

    with pytest.raises(RuntimeError, match="became unhealthy"):
        await update_helper.wait_for_health(client, "abc", attempts=1)

@pytest.mark.asyncio
async def test_wait_for_health_times_out(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(update_helper.asyncio, "sleep", no_sleep)

    client = HealthClient(
        [{"Running": True, "Health": {"Status": "starting"}}]
    )

    with pytest.raises(RuntimeError, match="Timed out"):
        await update_helper.wait_for_health(client, "abc", attempts=1)

def test_helper_read_status_handles_invalid_json(tmp_path, monkeypatch):
    path = tmp_path / "update-status.json"
    path.write_text("{broken", encoding="utf-8")

    monkeypatch.setattr(update_helper, "STATUS_PATH", path)

    assert update_helper.read_status() == {}

@pytest.mark.asyncio
async def test_remove_container_ignores_missing_container():
    class Client:
        async def get(self, path):
            return FakeResponse(status_code=404)

    await update_helper.remove_container(
        Client(),
        "missing123",
    )

@pytest.mark.asyncio
async def test_remove_running_container():
    calls = []

    class Client:
        async def get(self, path):
            return FakeResponse(
                {
                    "State": {
                        "Running": True,
                    }
                }
            )

        async def post(self, path, params=None):
            calls.append(("POST", path))
            return FakeResponse()

        async def delete(self, path, params=None):
            calls.append(("DELETE", path))
            return FakeResponse()

    await update_helper.remove_container(
        Client(),
        "abc123",
    )

    assert (
        "POST",
        "/containers/abc123/stop",
    ) in calls

    assert (
        "DELETE",
        "/containers/abc123",
    ) in calls

@pytest.mark.asyncio
async def test_create_and_start_container():
    calls = []

    class Client:
        async def post(self, path, params=None, json=None):
            calls.append(path)

            if path == "/containers/create":
                return FakeResponse({"Id": "new123"})

            return FakeResponse()

    result = await update_helper.create_and_start(
        Client(),
        "opencloudtouch",
        {"Image": "example:latest"},
    )

    assert result == "new123"
    assert calls == [
        "/containers/create",
        "/containers/new123/start",
    ]

@pytest.mark.asyncio
async def test_failed_rollback_sets_failed_status(
    tmp_path,
    monkeypatch,
):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path):
            return FakeResponse(old_inspect())

    monkeypatch.setattr(
        update_helper.httpx,
        "AsyncClient",
        lambda *args, **kwargs: Client(),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "update_helper",
            "old123",
            "example:1.5.9",
        ],
    )

    monkeypatch.setattr(
        update_helper,
        "STATUS_PATH",
        tmp_path / "update-status.json",
    )

    update_helper.STATUS_PATH.write_text(
        json.dumps(
            {
                "phase": "restarting",
                "current_version": "1.5.8",
                "target_version": "1.5.9",
            }
        ),
        encoding="utf-8",
    )

    async def remove(*args, **kwargs):
        pass

    create_count = 0

    async def create(*args, **kwargs):
        nonlocal create_count
        create_count += 1

        if create_count == 1:
            return "broken123"

        raise RuntimeError("rollback create failed")

    async def wait(*args, **kwargs):
        raise RuntimeError(
            "Updated container became unhealthy"
        )

    monkeypatch.setattr(
        update_helper,
        "remove_container",
        remove,
    )
    monkeypatch.setattr(
        update_helper,
        "create_and_start",
        create,
    )
    monkeypatch.setattr(
        update_helper,
        "wait_for_health",
        wait,
    )

    with pytest.raises(
        RuntimeError,
        match="rollback create failed",
    ):
        await update_helper.main()

    status = json.loads(
        update_helper.STATUS_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert status["phase"] == "failed"
    assert (
        status["rollback_error"]
        == "rollback create failed"
    )

@pytest.mark.asyncio
async def test_helper_preparation_failure_sets_failed(
    tmp_path,
    monkeypatch,
):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path):
            raise RuntimeError("inspect failed")

    monkeypatch.setattr(
        update_helper.httpx,
        "AsyncClient",
        lambda *args, **kwargs: Client(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "update_helper",
            "old123",
            "example:1.5.9",
        ],
    )
    monkeypatch.setattr(
        update_helper,
        "STATUS_PATH",
        tmp_path / "update-status.json",
    )

    with pytest.raises(
        RuntimeError,
        match="inspect failed",
    ):
        await update_helper.main()

    status = json.loads(
        update_helper.STATUS_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert status["phase"] == "failed"
    assert status["message"] == (
        "Update helper preparation failed"
    )

@pytest.mark.asyncio
async def test_start_failure_rolls_back_by_container_name(
    tmp_path,
    monkeypatch,
):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path):
            return FakeResponse(old_inspect())

    monkeypatch.setattr(
        update_helper.httpx,
        "AsyncClient",
        lambda *args, **kwargs: Client(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "update_helper",
            "old123",
            "example:1.5.9",
        ],
    )
    monkeypatch.setattr(
        update_helper,
        "STATUS_PATH",
        tmp_path / "update-status.json",
    )

    update_helper.STATUS_PATH.write_text(
        json.dumps(
            {
                "phase": "restarting",
                "current_version": "1.5.8",
                "target_version": "1.5.9",
            }
        ),
        encoding="utf-8",
    )

    removed = []
    create_count = 0

    async def remove(client, container_id):
        removed.append(container_id)

    async def create(client, name, config):
        nonlocal create_count
        create_count += 1

        if create_count == 1:
            raise RuntimeError("container start failed")

        return "rollback123"

    async def wait(client, container_id, attempts=45):
        pass

    monkeypatch.setattr(
        update_helper,
        "remove_container",
        remove,
    )
    monkeypatch.setattr(
        update_helper,
        "create_and_start",
        create,
    )
    monkeypatch.setattr(
        update_helper,
        "wait_for_health",
        wait,
    )

    with pytest.raises(SystemExit):
        await update_helper.main()

    assert removed == [
        "old123",
        "opencloudtouch",
    ]
    assert create_count == 2

    status = json.loads(
        update_helper.STATUS_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert status["phase"] == "rolled_back"
    assert status["current_version"] == "1.5.8"
    assert status["error"] == "container start failed"
