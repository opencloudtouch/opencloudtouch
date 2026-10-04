import httpx
import pytest

from opencloudtouch.system import update_service


class FakeResponse:
    def __init__(self, data=None, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(
                f"HTTP {self.status_code}"
            )


class FakeStream:
    def __init__(self, lines):
        self.lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeClient:
    def __init__(self):
        self.requests = []

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
        self.requests.append(("GET", path))

        if path == "/containers/json":
            return FakeResponse(
                [
                    {
                        "Id": "oct123",
                        "Names": ["/opencloudtouch"],
                    }
                ]
            )

        if path == "/containers/oct123/json":
            return FakeResponse(
                {
                    "Image": "sha256:oldimage",
                    "Config": {
                        "Image": (
                            "ghcr.io/opencloudtouch/"
                            "opencloudtouch:1.5.8"
                        )
                    },
                    "Mounts": [
                        {
                            "Type": "volume",
                            "Name": "oct-data",
                            "Destination": "/data",
                        }
                    ],
                }
            )

        raise AssertionError(
            f"Unexpected GET {path}"
        )

    async def post(
        self,
        path,
        params=None,
        json=None,
    ):
        self.requests.append(
            ("POST", path, params, json)
        )

        if path == "/containers/create":
            return FakeResponse(
                {"Id": "helper123"}
            )

        if path == "/containers/helper123/start":
            return FakeResponse()

        raise AssertionError(
            f"Unexpected POST {path}"
        )

    def stream(
        self,
        method,
        path,
        params=None,
    ):
        self.requests.append(
            (method, path, params)
        )

        return FakeStream(
            [
                (
                    '{"status":"Downloading",'
                    '"id":"layer1",'
                    '"progressDetail":'
                    '{"current":50,"total":100}}'
                ),
                (
                    '{"status":"Download complete",'
                    '"id":"layer1",'
                    '"progressDetail":'
                    '{"current":100,"total":100}}'
                ),
            ]
        )


def test_parse_version():
    assert update_service.parse_version(
        "1.5.8"
    ) == (1, 5, 8)

    assert update_service.parse_version(
        "v2.0.1"
    ) == (2, 0, 1)


def test_parse_version_rejects_invalid():
    with pytest.raises(ValueError):
        update_service.parse_version("latest")


def test_target_image_uses_release_tag():
    assert (
        update_service.target_image_for_version(
            "1.5.9"
        )
        == (
            "ghcr.io/opencloudtouch/"
            "opencloudtouch:1.5.9"
        )
    )


def test_split_image_reference():
    assert update_service.split_image_reference(
        "ghcr.io/opencloudtouch/opencloudtouch:1.5.9"
    ) == (
        "ghcr.io/opencloudtouch/opencloudtouch",
        "1.5.9",
    )


def test_split_image_reference_defaults_latest():
    assert update_service.split_image_reference(
        "ghcr.io/opencloudtouch/opencloudtouch"
    ) == (
        "ghcr.io/opencloudtouch/opencloudtouch",
        "latest",
    )


@pytest.mark.asyncio
async def test_check_for_update_official(
    monkeypatch,
):
    async def fake_release():
        return {
            "latest": "1.5.9",
            "release_url": (
                "https://example.test/v1.5.9"
            ),
        }

    monkeypatch.setattr(
        update_service,
        "get_latest_release",
        fake_release,
    )
    monkeypatch.setattr(
        update_service,
        "__version__",
        "1.5.8",
    )
    monkeypatch.setattr(
        update_service,
        "is_official_build",
        lambda: True,
    )

    result = (
        await update_service.check_for_update()
    )

    assert result == {
        "current": "1.5.8",
        "latest": "1.5.9",
        "update_available": True,
        "release_url": (
            "https://example.test/v1.5.9"
        ),
    }


@pytest.mark.asyncio
async def test_check_for_update_no_downgrade(
    monkeypatch,
):
    async def fake_release():
        return {
            "latest": "1.5.7",
            "release_url": (
                "https://example.test/v1.5.7"
            ),
        }

    monkeypatch.setattr(
        update_service,
        "get_latest_release",
        fake_release,
    )
    monkeypatch.setattr(
        update_service,
        "__version__",
        "1.5.8",
    )
    monkeypatch.setattr(
        update_service,
        "is_official_build",
        lambda: True,
    )

    result = (
        await update_service.check_for_update()
    )

    assert result["update_available"] is False


@pytest.mark.asyncio
async def test_community_build_not_updateable(
    monkeypatch,
):
    async def fake_release():
        return {
            "latest": "1.5.9",
            "release_url": (
                "https://example.test/v1.5.9"
            ),
        }

    monkeypatch.setattr(
        update_service,
        "get_latest_release",
        fake_release,
    )
    monkeypatch.setattr(
        update_service,
        "__version__",
        "1.5.8",
    )
    monkeypatch.setattr(
        update_service,
        "is_official_build",
        lambda: False,
    )

    result = (
        await update_service.check_for_update()
    )

    assert result["update_available"] is False


@pytest.mark.asyncio
async def test_get_oct_container(monkeypatch):
    client = FakeClient()

    async def fake_get_docker_client():
        return client

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_get_docker_client,
    )

    container = (
        await update_service.get_oct_container()
    )

    assert container["Id"] == "oct123"


@pytest.mark.asyncio
async def test_pull_oct_image_reports_progress(
    monkeypatch,
):
    client = FakeClient()
    progress = []

    async def fake_get_docker_client():
        return client

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_get_docker_client,
    )

    await update_service.pull_oct_image(
        (
            "ghcr.io/opencloudtouch/"
            "opencloudtouch:1.5.9"
        ),
        lambda pct, message: progress.append(
            (pct, message)
        ),
    )

    assert progress
    assert progress[-1] == (
        90,
        "Image download complete",
    )


@pytest.mark.asyncio
async def test_launch_helper_uses_old_image(
    monkeypatch,
):
    client = FakeClient()

    async def fake_get_docker_client():
        return client

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_get_docker_client,
    )

    helper_id = (
        await update_service.launch_update_helper(
            "oct123",
            (
                "ghcr.io/opencloudtouch/"
                "opencloudtouch:1.5.9"
            ),
        )
    )

    assert helper_id == "helper123"

    create_request = next(
        request
        for request in client.requests
        if request[0:2]
        == ("POST", "/containers/create")
    )

    assert create_request[2] is None

    config = create_request[3]

    assert config["Image"] == (
        "sha256:oldimage"
    )

    assert config["Cmd"][-1] == (
        "ghcr.io/opencloudtouch/"
        "opencloudtouch:1.5.9"
    )

    assert (
        "oct-data:/oct-update-data:rw"
        in config["HostConfig"]["Binds"]
    )


class AsyncClient:
    def __init__(self, response=None):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, path):
        return self.response

@pytest.mark.asyncio
async def test_get_latest_release_success(monkeypatch):
    client = AsyncClient(
        FakeResponse(
            {
                "tag_name": "v1.5.9",
                "html_url": "https://example.test/v1.5.9",
            }
        )
    )

    monkeypatch.setattr(
        update_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client,
    )

    result = await update_service.get_latest_release()

    assert result == {
        "latest": "1.5.9",
        "release_url": "https://example.test/v1.5.9",
    }

@pytest.mark.asyncio
async def test_get_latest_release_rejects_missing_tag(monkeypatch):
    client = AsyncClient(
        FakeResponse(
            {
                "html_url": "https://example.test/release",
            }
        )
    )

    monkeypatch.setattr(
        update_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client,
    )

    with pytest.raises(
        update_service.UpdateCheckError,
        match="tag_name",
    ):
        await update_service.get_latest_release()

@pytest.mark.asyncio
async def test_get_latest_release_handles_network_error(monkeypatch):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(
        update_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: Client(),
    )

    with pytest.raises(
        update_service.UpdateCheckError,
        match="Failed to check",
    ):
        await update_service.get_latest_release()

@pytest.mark.asyncio
async def test_get_oct_container_returns_none(monkeypatch):
    client = AsyncClient(
        FakeResponse(
            [
                {
                    "Id": "other123",
                    "Names": ["/something-else"],
                }
            ]
        )
    )

    async def fake_client():
        return client

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_client,
    )

    assert await update_service.get_oct_container() is None

@pytest.mark.asyncio
async def test_get_container_inspect(monkeypatch):
    expected = {
        "Id": "abc123",
        "Image": "sha256:test",
    }

    client = AsyncClient(FakeResponse(expected))

    async def fake_client():
        return client

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_client,
    )

    assert (
        await update_service.get_container_inspect("abc123")
        == expected
    )

@pytest.mark.asyncio
async def test_launch_helper_rejects_unsupported_mount(monkeypatch):
    client = AsyncClient(
        FakeResponse(
            {
                "Image": "sha256:old",
                "Mounts": [
                    {
                        "Type": "tmpfs",
                        "Destination": "/data",
                    }
                ],
            }
        )
    )

    async def fake_client():
        return client

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_client,
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported /data mount type",
    ):
        await update_service.launch_update_helper(
            "old123",
            "ghcr.io/opencloudtouch/opencloudtouch:1.5.9",
        )

def test_split_image_reference_rejects_digest():
    with pytest.raises(ValueError, match="Digest"):
        update_service.split_image_reference(
            "ghcr.io/opencloudtouch/opencloudtouch@sha256:abc"
        )

@pytest.mark.asyncio
async def test_launch_helper_supports_bind_mount(monkeypatch):
    created = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path):
            return FakeResponse(
                {
                    "Image": "sha256:old",
                    "Mounts": [
                        {
                            "Type": "bind",
                            "Source": "/srv/oct-data",
                            "Destination": "/data",
                        }
                    ],
                }
            )

        async def post(self, path, params=None, json=None):
            if path == "/containers/create":
                created["config"] = json
                return FakeResponse({"Id": "helper123"})
            return FakeResponse()

    async def fake_client():
        return Client()

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_client,
    )

    result = await update_service.launch_update_helper(
        "old123",
        "ghcr.io/opencloudtouch/opencloudtouch:1.5.9",
    )

    assert result == "helper123"
    assert (
        "/srv/oct-data:/oct-update-data:rw"
        in created["config"]["HostConfig"]["Binds"]
    )

@pytest.mark.asyncio
async def test_launch_helper_requires_data_mount(monkeypatch):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, path):
            return FakeResponse(
                {
                    "Image": "sha256:old",
                    "Mounts": [],
                }
            )

    async def fake_client():
        return Client()

    monkeypatch.setattr(
        update_service,
        "get_docker_client",
        fake_client,
    )

    with pytest.raises(RuntimeError, match="/data mount not found"):
        await update_service.launch_update_helper(
            "old123",
            "ghcr.io/opencloudtouch/opencloudtouch:1.5.9",
        )
