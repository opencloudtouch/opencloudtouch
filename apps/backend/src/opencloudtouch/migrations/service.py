"""Run ordered, logged migration steps per speaker (decisions 18-20)."""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping

from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.migrations.repository import SpeakerMigrationRepository

logger = logging.getLogger(__name__)

MigrationStep = Callable[[Device], Awaitable[None]]

# "From version" -> step. Step 0->1 stays unregistered until verified on hardware
# (decision 20), so every speaker stays on version 0.
STEPS: dict[int, MigrationStep] = {}


class SpeakerMigrationService:
    """Bring each speaker from its stored version through the registered steps.

    Steps must be idempotent: a step that failed half-way runs again from the
    start on the next run (startup or when the speaker comes back).
    """

    def __init__(
        self,
        repo: SpeakerMigrationRepository,
        device_repo: DeviceRepository,
        steps: Mapping[int, MigrationStep] = STEPS,
    ) -> None:
        self._repo = repo
        self._device_repo = device_repo
        self._steps = steps
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def run(self, device: Device) -> int:
        """Run pending steps for one speaker; return the version it is on."""
        device_id = device.device_id
        async with self._locks[device_id]:
            version, _ = await self._repo.get(device_id)
            while version in self._steps:
                logger.info(
                    "[MIGRATION] %s step %d->%d start", device_id, version, version + 1
                )
                started = time.monotonic()
                try:
                    await self._steps[version](device)
                except (
                    Exception
                ) as exc:  # noqa: BLE001 - a step failure must not stop OCT
                    reason = f"{type(exc).__name__}: {exc}"
                    await self._repo.set_error(device_id, reason)
                    logger.warning(
                        "[MIGRATION] %s step %d->%d failed after %d ms: %s",
                        device_id,
                        version,
                        version + 1,
                        (time.monotonic() - started) * 1000,
                        reason,
                    )
                    return version
                version += 1
                await self._repo.set_version(device_id, version)
                logger.info(
                    "[MIGRATION] %s step %d->%d ok in %d ms",
                    device_id,
                    version - 1,
                    version,
                    (time.monotonic() - started) * 1000,
                )
            await self._repo.set_version(device_id, version)
            logger.info(
                "[MIGRATION] %s on version %d, no pending step", device_id, version
            )
            return version

    async def run_all(self) -> None:
        """Run every registered speaker; one speaker's failure never stops the rest."""
        for device in await self._device_repo.get_all():
            try:
                await self.run(device)
            except Exception:  # noqa: BLE001
                logger.exception("[MIGRATION] %s run failed", device.device_id)

    async def status(self, device_id: str) -> tuple[int, str | None]:
        """Return (version, last_error) of one speaker."""
        return await self._repo.get(device_id)

    async def on_connection_state(self, device_id: str, state: ConnectionState) -> None:
        """WebSocket state hook: run migrations when a speaker (re)connects."""
        if state != ConnectionState.CONNECTED:
            return
        device = await self._device_repo.get_by_device_id(device_id)
        if device is not None:
            await self.run(device)
