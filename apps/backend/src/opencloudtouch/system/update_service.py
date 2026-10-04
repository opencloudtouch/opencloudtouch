import json
import re
from collections.abc import Callable
from typing import Any

import httpx

from opencloudtouch import __version__, is_official_build


DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_BASE_URL = "http://docker"

GITHUB_RELEASE_URL = (
    "https://api.github.com/repos/opencloudtouch/"
    "opencloudtouch/releases/latest"
)
OFFICIAL_IMAGE_REPOSITORY = "ghcr.io/opencloudtouch/opencloudtouch"

_VERSION_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$"
)


class UpdateCheckError(RuntimeError):
    """Raised when release information cannot be retrieved."""


def parse_version(version: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(version.strip())

    if match is None:
        raise ValueError(f"Unsupported version format: {version}")

    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def target_image_for_version(version: str) -> str:
    normalized = version.removeprefix("v")
    parse_version(normalized)
    return f"{OFFICIAL_IMAGE_REPOSITORY}:{normalized}"


async def get_latest_release() -> dict[str, str]:
    timeout = httpx.Timeout(
        connect=5.0,
        read=10.0,
        write=10.0,
        pool=5.0,
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "OpenCloudTouch",
            },
        ) as client:
            response = await client.get(GITHUB_RELEASE_URL)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise UpdateCheckError(
            f"Failed to check GitHub Releases: {exc}"
        ) from exc

    release: dict[str, Any] = response.json()

    tag_name = release.get("tag_name")
    release_url = release.get("html_url")

    if not isinstance(tag_name, str) or not tag_name:
        raise UpdateCheckError(
            "GitHub release response has no valid tag_name"
        )

    if not isinstance(release_url, str) or not release_url:
        raise UpdateCheckError(
            "GitHub release response has no valid html_url"
        )

    latest = tag_name.removeprefix("v")

    try:
        parse_version(latest)
    except ValueError as exc:
        raise UpdateCheckError(str(exc)) from exc

    return {
        "latest": latest,
        "release_url": release_url,
    }


async def check_for_update() -> dict[str, Any]:
    release = await get_latest_release()

    current = __version__
    latest = release["latest"]

    try:
        newer = parse_version(latest) > parse_version(current)
    except ValueError as exc:
        raise UpdateCheckError(str(exc)) from exc

    return {
        "current": current,
        "latest": latest,
        "update_available": is_official_build() and newer,
        "release_url": release["release_url"],
    }


async def get_docker_client():
    transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET)

    timeout = httpx.Timeout(
        connect=5.0,
        read=300.0,
        write=30.0,
        pool=5.0,
    )

    return httpx.AsyncClient(
        transport=transport,
        base_url=DOCKER_BASE_URL,
        timeout=timeout,
    )


async def get_oct_container():
    async with await get_docker_client() as client:
        response = await client.get("/containers/json")
        response.raise_for_status()

        for container in response.json():
            if "/opencloudtouch" in container.get("Names", []):
                return container

    return None


async def get_container_inspect(container_id: str):
    async with await get_docker_client() as client:
        response = await client.get(
            f"/containers/{container_id}/json"
        )
        response.raise_for_status()
        return response.json()


def split_image_reference(image: str) -> tuple[str, str]:
    if "@" in image:
        raise ValueError("Digest image references are not supported")

    final_component = image.rsplit("/", 1)[-1]

    if ":" not in final_component:
        return image, "latest"

    repository, tag = image.rsplit(":", 1)
    return repository, tag


async def pull_oct_image(
    image: str,
    progress_callback: Callable[[int, str], None] | None = None,
):
    repository, tag = split_image_reference(image)

    layer_progress: dict[str, tuple[int, int]] = {}
    last_progress = 0
    last_status = None

    async with await get_docker_client() as client:
        async with client.stream(
            "POST",
            "/images/create",
            params={
                "fromImage": repository,
                "tag": tag,
            },
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                last_status = line

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                error = event.get("error")
                if error:
                    raise RuntimeError(str(error))

                layer_id = event.get("id")
                detail = event.get("progressDetail") or {}

                current = detail.get("current")
                total = detail.get("total")

                if (
                    isinstance(layer_id, str)
                    and isinstance(current, int)
                    and isinstance(total, int)
                    and total > 0
                ):
                    layer_progress[layer_id] = (
                        min(current, total),
                        total,
                    )

                    downloaded = sum(
                        value[0]
                        for value in layer_progress.values()
                    )
                    total_size = sum(
                        value[1]
                        for value in layer_progress.values()
                    )

                    if total_size > 0:
                        progress = min(
                            89,
                            5 + int(
                                downloaded
                                / total_size
                                * 84
                            ),
                        )

                        if (
                            progress_callback is not None
                            and progress >= last_progress + 2
                        ):
                            progress_callback(
                                progress,
                                "Pulling new image...",
                            )
                            last_progress = progress

    if progress_callback is not None:
        progress_callback(
            90,
            "Image download complete",
        )

    return last_status


async def launch_update_helper(
    target_container_id: str,
    target_image: str,
):
    async with await get_docker_client() as client:
        inspect_response = await client.get(
            f"/containers/{target_container_id}/json"
        )
        inspect_response.raise_for_status()
        inspect = inspect_response.json()

        data_mount = next(
            (
                mount
                for mount in inspect.get("Mounts", [])
                if mount.get("Destination") == "/data"
            ),
            None,
        )

        if data_mount is None:
            raise RuntimeError(
                "OpenCloudTouch /data mount not found"
            )

        if data_mount["Type"] == "volume":
            data_bind = (
                f'{data_mount["Name"]}:'
                "/oct-update-data:rw"
            )
        elif data_mount["Type"] == "bind":
            data_bind = (
                f'{data_mount["Source"]}:'
                "/oct-update-data:rw"
            )
        else:
            raise RuntimeError(
                "Unsupported /data mount type: "
                f'{data_mount["Type"]}'
            )

        # Run the helper from the currently working immutable image.
        # The helper can therefore recover even if the new image is broken.
        helper_image = inspect["Image"]

        helper_config = {
            "Image": helper_image,
            "Entrypoint": ["python"],
            "Cmd": [
                "-m",
                "opencloudtouch.system.update_helper",
                target_container_id,
                target_image,
            ],
            "Env": [
                "OCT_UPDATE_STATUS_PATH="
                "/oct-update-data/update-status.json",
            ],
            "HostConfig": {
                "Binds": [
                    "/var/run/docker.sock:"
                    "/var/run/docker.sock",
                    data_bind,
                ],
                "AutoRemove": True,
            },
        }

        response = await client.post(
            "/containers/create",
            json=helper_config,
        )
        response.raise_for_status()

        helper_id = response.json()["Id"]

        response = await client.post(
            f"/containers/{helper_id}/start"
        )
        response.raise_for_status()

        return helper_id
