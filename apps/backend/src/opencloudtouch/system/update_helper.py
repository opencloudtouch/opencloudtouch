"""External helper for replacing the running OCT container."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


DOCKER_SOCKET = "/var/run/docker.sock"
STATUS_PATH = Path(
    os.getenv(
        "OCT_UPDATE_STATUS_PATH",
        "/oct-update-data/update-status.json",
    )
)


def read_status() -> dict[str, Any]:
    try:
        return json.loads(
            STATUS_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}


def set_status(
    phase: str,
    *,
    progress_pct: int,
    message: str,
    **extra: Any,
) -> None:
    data = {
        **read_status(),
        "phase": phase,
        "progress_pct": progress_pct,
        "message": message,
        **extra,
    }

    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data),
        encoding="utf-8",
    )
    tmp.replace(STATUS_PATH)


async def wait_for_health(
    client: httpx.AsyncClient,
    container_id: str,
    attempts: int = 45,
) -> None:
    for _ in range(attempts):
        await asyncio.sleep(2)

        response = await client.get(
            f"/containers/{container_id}/json"
        )
        response.raise_for_status()

        inspect = response.json()
        state = inspect["State"]

        if not state.get("Running"):
            raise RuntimeError(
                "Updated container stopped unexpectedly"
            )

        health = (
            state.get("Health", {})
            .get("Status")
        )

        if health == "healthy":
            return

        if health == "unhealthy":
            raise RuntimeError(
                "Updated container became unhealthy"
            )

    raise RuntimeError(
        "Timed out waiting for updated container health"
    )


def build_container_config(
    inspect: dict,
    image: str | None = None,
) -> dict:
    # Keep deployment/runtime settings, but inherit image defaults from the selected image.
    env = [
        value
        for value in inspect["Config"].get("Env", [])
        if value.startswith("OCT_")
        and not value.startswith("OCT_BUILD_SIGNATURE=")
        and not value.startswith("OCT_VERSION=")
    ]

    labels = {
        key: value
        for key, value in inspect["Config"].get("Labels", {}).items()
        if key.startswith("com.docker.compose.")
        and key not in {
            "com.docker.compose.image",
            "com.docker.compose.config-hash",
        }
    }

    config = {
        "Image": image or inspect["Config"]["Image"],
        "Env": env,
        "HostConfig": {
            "NetworkMode": inspect["HostConfig"]["NetworkMode"],
            "Binds": inspect["HostConfig"].get("Binds"),
            "RestartPolicy": inspect["HostConfig"]["RestartPolicy"],
            "LogConfig": inspect["HostConfig"].get("LogConfig"),
            "ShmSize": inspect["HostConfig"].get("ShmSize"),
            "PortBindings": inspect["HostConfig"].get("PortBindings"),
            "PublishAllPorts": inspect["HostConfig"].get("PublishAllPorts"),
        },
    }

    if labels:
        config["Labels"] = labels

    healthcheck = inspect["Config"].get("Healthcheck")
    if healthcheck is not None:
        config["Healthcheck"] = healthcheck

    return config


async def remove_container(
    client: httpx.AsyncClient,
    container_id: str,
) -> None:
    inspect_response = await client.get(
        f"/containers/{container_id}/json"
    )

    if inspect_response.status_code == 404:
        return

    inspect_response.raise_for_status()
    inspect = inspect_response.json()

    if inspect["State"].get("Running"):
        response = await client.post(
            f"/containers/{container_id}/stop",
            params={"t": 10},
        )
        response.raise_for_status()

    response = await client.delete(
        f"/containers/{container_id}",
        params={"force": "true"},
    )
    response.raise_for_status()


async def create_and_start(
    client: httpx.AsyncClient,
    name: str,
    config: dict,
) -> str:
    response = await client.post(
        "/containers/create",
        params={"name": name},
        json=config,
    )
    response.raise_for_status()

    container_id = response.json()["Id"]

    response = await client.post(
        f"/containers/{container_id}/start"
    )
    response.raise_for_status()

    return container_id


async def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m "
            "opencloudtouch.system.update_helper "
            "<container_id> <target_image>"
        )

    container_id = sys.argv[1]
    target_image = sys.argv[2]

    transport = httpx.AsyncHTTPTransport(
        uds=DOCKER_SOCKET
    )

    timeout = httpx.Timeout(
        connect=5.0,
        read=120.0,
        write=30.0,
        pool=5.0,
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://docker",
        timeout=timeout,
    ) as client:
        try:
            response = await client.get(
                f"/containers/{container_id}/json"
            )
            response.raise_for_status()
            inspect = response.json()

            name = inspect["Name"].lstrip("/")
            old_image_id = inspect["Image"]

            status = read_status()
            previous_version = status.get(
                "current_version"
            )
            target_version = status.get(
                "target_version"
            )

            new_config = build_container_config(
                inspect,
                target_image,
            )
            rollback_config = build_container_config(
                inspect,
                old_image_id,
            )
        except Exception as preparation_error:
            set_status(
                "failed",
                progress_pct=100,
                message="Update helper preparation failed",
                error=str(preparation_error),
            )
            raise

        new_container_id = None

        try:
            await remove_container(
                client,
                container_id,
            )

            new_container_id = (
                await create_and_start(
                    client,
                    name,
                    new_config,
                )
            )

            await wait_for_health(
                client,
                new_container_id,
            )

            set_status(
                "ready",
                progress_pct=100,
                message="Update complete",
                container_id=new_container_id,
                image=target_image,
                current_version=target_version,
            )

            print(
                f"Replaced {name}: "
                f"{container_id} -> "
                f"{new_container_id}"
            )

        except Exception as update_error:
            set_status(
                "rolling_back",
                progress_pct=95,
                message=(
                    "Update failed; restoring "
                    "previous version"
                ),
                error=str(update_error),
            )

            try:
                # Also handles a container that was created but failed to start.
                await remove_container(
                    client,
                    name,
                )

                rollback_container_id = (
                    await create_and_start(
                        client,
                        name,
                        rollback_config,
                    )
                )

                await wait_for_health(
                    client,
                    rollback_container_id,
                )

                set_status(
                    "rolled_back",
                    progress_pct=100,
                    message=(
                        "Previous version restored"
                    ),
                    container_id=(
                        rollback_container_id
                    ),
                    image=old_image_id,
                    current_version=(
                        previous_version
                    ),
                    error=str(update_error),
                )

                print(
                    "Rollback completed for "
                    f"{name}: "
                    f"{rollback_container_id}"
                )

            except Exception as rollback_error:
                set_status(
                    "failed",
                    progress_pct=100,
                    message=(
                        "Update and rollback failed"
                    ),
                    error=str(update_error),
                    rollback_error=str(
                        rollback_error
                    ),
                )
                raise

            raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(main())
