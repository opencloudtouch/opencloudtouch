"""External helper for replacing the running OCT container."""

import asyncio
import importlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DOCKER_SOCKET = "/var/run/docker.sock"
logger = logging.getLogger(__name__)
STATUS_PATH = Path(
    os.getenv(
        "OCT_UPDATE_STATUS_PATH",
        "/oct-update-data/update-status.json",
    )
)


def _get_effective_uid() -> int:
    return getattr(os, "geteuid", lambda: -1)()


def _chown(path: Path, uid: int, gid: int) -> None:
    os.chown(path, uid, gid)  # type: ignore[attr-defined]


def _oct_user_ids() -> tuple[int, int]:
    oct_user = importlib.import_module("pwd").getpwnam("oct")
    return oct_user.pw_uid, oct_user.pw_gid


def read_status() -> dict[str, Any]:
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
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
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **extra,
    }

    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data),
        encoding="utf-8",
    )
    # Keep the status file writable by the non-root OCT server after replacement.
    if _get_effective_uid() == 0:
        uid, gid = _oct_user_ids()
        _chown(tmp, uid, gid)

    tmp.replace(STATUS_PATH)


async def wait_for_health(
    client: httpx.AsyncClient,
    container_id: str,
    attempts: int = 45,
    no_healthcheck_grace_attempts: int = 5,
) -> None:
    for attempt in range(attempts):
        await asyncio.sleep(2)

        response = await client.get(f"/containers/{container_id}/json")
        response.raise_for_status()

        inspect = response.json()
        state = inspect["State"]

        if not state.get("Running"):
            raise RuntimeError("Updated container stopped unexpectedly")

        health = state.get("Health", {}).get("Status")

        if health is None and (
            state.get("Restarting") or inspect.get("RestartCount", 0) > 0
        ):
            raise RuntimeError(
                "Updated container restarted during healthcheck grace period"
            )

        if health is None and attempt + 1 >= no_healthcheck_grace_attempts:
            logger.warning(
                "Updated container has no healthcheck; accepting running state"
            )
            return

        if health == "healthy":
            return

        if health == "unhealthy":
            raise RuntimeError("Updated container became unhealthy")

    raise RuntimeError("Timed out waiting for updated container health")


def _mount_config(inspect: dict) -> list[dict[str, Any]]:
    mounts = []
    for mount in inspect.get("Mounts") or []:
        mount_type = mount.get("Type")
        target = mount.get("Destination")
        if not isinstance(mount_type, str) or not isinstance(target, str):
            continue

        config: dict[str, Any] = {
            "Type": mount_type,
            "Target": target,
            "ReadOnly": not mount.get("RW", True),
        }
        source = mount.get("Name") if mount_type == "volume" else mount.get("Source")
        if source:
            config["Source"] = source
        mounts.append(config)

    if not any(mount.get("Target") == "/data" for mount in mounts):
        raise RuntimeError("Refusing update: replacement config has no /data mount")

    return mounts


def build_container_config(
    inspect: dict,
    image: str | None = None,
) -> dict:
    # Keep deployment/runtime settings, but inherit image defaults from the selected image.
    env = [
        value
        for value in inspect["Config"].get("Env", [])
        if (
            value.startswith(("OCT_", "TZ="))
            or value.upper().startswith(("HTTP_PROXY=", "HTTPS_PROXY=", "NO_PROXY="))
        )
        and not value.startswith("OCT_BUILD_SIGNATURE=")
        and not value.startswith("OCT_VERSION=")
    ]

    labels = {
        key: value
        for key, value in inspect["Config"].get("Labels", {}).items()
        if key.startswith("com.docker.compose.")
        and key
        not in {
            "com.docker.compose.image",
            "com.docker.compose.config-hash",
        }
    }

    config = {
        "Image": image or inspect["Config"]["Image"],
        "Env": env,
        "HostConfig": {
            "NetworkMode": inspect["HostConfig"]["NetworkMode"],
            "Mounts": _mount_config(inspect),
            "RestartPolicy": inspect["HostConfig"]["RestartPolicy"],
            "LogConfig": inspect["HostConfig"].get("LogConfig"),
            "ShmSize": inspect["HostConfig"].get("ShmSize"),
            "PortBindings": inspect["HostConfig"].get("PortBindings"),
            "PublishAllPorts": inspect["HostConfig"].get("PublishAllPorts"),
        },
    }

    if labels:
        config["Labels"] = labels

    return config


async def remove_container(
    client: httpx.AsyncClient,
    container_id: str,
) -> None:
    inspect_response = await client.get(f"/containers/{container_id}/json")

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

    response = await client.post(f"/containers/{container_id}/start")
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

    transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET)

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
            response = await client.get(f"/containers/{container_id}/json")
            response.raise_for_status()
            inspect = response.json()

            name = inspect["Name"].lstrip("/")
            old_image_id = inspect["Image"]

            status = read_status()
            previous_version = status.get("current_version")
            target_version = status.get("target_version")

            new_config = build_container_config(
                inspect,
                target_image,
            )
            rollback_config = build_container_config(
                inspect,
                old_image_id,
            )
        except Exception as preparation_error:
            logger.exception("Update helper preparation failed")
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

            new_container_id = await create_and_start(
                client,
                name,
                new_config,
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

            print(f"Replaced {name}: {container_id} -> {new_container_id}")

        except Exception as update_error:
            logger.exception("Updated container failed; starting rollback")
            set_status(
                "rolling_back",
                progress_pct=95,
                message=("Update failed; restoring previous version"),
                error=str(update_error),
            )

            try:
                # Also handles a container that was created but failed to start.
                await remove_container(
                    client,
                    name,
                )

                rollback_container_id = await create_and_start(
                    client,
                    name,
                    rollback_config,
                )

                await wait_for_health(
                    client,
                    rollback_container_id,
                )

                set_status(
                    "rolled_back",
                    progress_pct=100,
                    message=("Previous version restored"),
                    container_id=(rollback_container_id),
                    image=old_image_id,
                    current_version=(previous_version),
                    error=str(update_error),
                )

                print(f"Rollback completed for {name}: {rollback_container_id}")

            except Exception as rollback_error:
                logger.exception("Self-update rollback failed")
                set_status(
                    "failed",
                    progress_pct=100,
                    message=("Update and rollback failed"),
                    error=str(update_error),
                    rollback_error=str(rollback_error),
                )
                raise

            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
