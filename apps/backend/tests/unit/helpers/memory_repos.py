"""In-memory repositories: no threads, so virtual-time tests stay deterministic."""

import copy

from opencloudtouch.sleep_timer.models import SleepTimer


class InMemorySleepTimerRepository:
    def __init__(self) -> None:
        self.rows: dict[str, SleepTimer] = {}

    async def get(self, device_id: str) -> SleepTimer | None:
        row = self.rows.get(device_id)
        return copy.copy(row) if row else None

    async def list_all(self) -> list[SleepTimer]:
        return sorted(
            (copy.copy(r) for r in self.rows.values()), key=lambda r: r.ends_at
        )

    async def upsert(self, timer: SleepTimer) -> None:
        self.rows[timer.device_id] = copy.copy(timer)

    async def set_original_volume(self, device_id: str, volume: int | None) -> None:
        if device_id in self.rows:
            self.rows[device_id].original_volume = volume

    async def delete(self, device_id: str) -> None:
        self.rows.pop(device_id, None)
