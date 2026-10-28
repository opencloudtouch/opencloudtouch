"""A fake DeviceService for volume/playback logic (live calls, scripted failures)."""

from collections.abc import Callable

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo


class FakePlaybackDevices:
    """Volume, mute and now-playing state of one device plus a call log."""

    def __init__(self, device_id: str = "AABBCC112233") -> None:
        self.device_id = device_id
        self.volume = 40
        self.muted = False
        self.source = "INTERNET_RADIO"
        self.state = "PLAY_STATE"
        self.calls: list[tuple] = []
        self.missing = False
        # name -> list of exceptions (None = succeed) consumed call by call
        self.failures: dict[str, list[BaseException | None]] = {}
        # state change applied by a key press, e.g. {"PAUSE": "PAUSE_STATE"}
        self.key_effects: dict[str, str] = {
            "PAUSE": "PAUSE_STATE",
            "STOP": "STOP_STATE",
        }
        self.on_call: Callable[[str, tuple], None] | None = None

    def _enter(self, name: str, *args) -> None:
        self.calls.append((name, *args))
        if self.on_call is not None:
            self.on_call(name, args)
        if self.missing:
            raise DeviceNotFoundError(self.device_id)
        queue = self.failures.get(name)
        if queue:
            error = queue.pop(0)
            if error is not None:
                raise error

    async def get_device_by_id(self, device_id: str):
        return None if self.missing else object()

    async def get_volume(self, device_id: str) -> VolumeInfo:
        self._enter("get_volume")
        return VolumeInfo(actual=self.volume, target=self.volume, muted=self.muted)

    async def set_volume(self, device_id: str, level: int) -> VolumeInfo:
        self._enter("set_volume", level)
        self.volume = max(0, min(100, level))
        return VolumeInfo(actual=self.volume, target=self.volume, muted=self.muted)

    async def get_now_playing(self, device_id: str) -> NowPlayingInfo:
        self._enter("get_now_playing")
        return NowPlayingInfo(source=self.source, state=self.state)

    async def press_key(self, device_id: str, key: str, state: str = "both") -> None:
        self._enter("press_key", key)
        if key == "POWER":
            if self.source == "STANDBY":
                self.source, self.state = "INTERNET_RADIO", "PLAY_STATE"
            else:
                self.source, self.state = "STANDBY", "STOP_STATE"
        elif key in self.key_effects and self.state == "PLAY_STATE":
            self.state = self.key_effects[key]

    # ---- assertions helpers ----

    def volumes_set(self) -> list[int]:
        return [c[1] for c in self.calls if c[0] == "set_volume"]

    def keys(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == "press_key"]

    def fail(self, name: str, *errors: BaseException | None) -> None:
        self.failures.setdefault(name, []).extend(errors)


def unreachable() -> DeviceConnectionError:
    return DeviceConnectionError("192.0.2.1", "connection refused")
