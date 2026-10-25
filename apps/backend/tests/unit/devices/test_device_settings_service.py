"""DeviceService: reading and writing language, clock and power saving."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
    DeviceRejectedError,
)
from opencloudtouch.devices.client import (
    ClockSetting,
    LanguageSetting,
    PowerSavingSetting,
)
from opencloudtouch.devices.device_settings import LANGUAGES
from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.service import DeviceService


class FakeSettingsClient:
    """Stateful stand-in for a speaker client; records the order of calls."""

    def __init__(self):
        self.language = LanguageSetting(2, "Deutsch")
        self.clock = ClockSetting(
            True,
            "24h",
            "Europe/Berlin",
            {"userOffsetMinute": "0", "userUtcTime": "0", "brightnessLevel": "3"},
        )
        self.power = PowerSavingSetting(False)
        self.calls: list[str] = []
        self.read_errors: dict[str, BaseException] = {}
        self.post_error: BaseException | None = None
        self.keep_old_value = False  # speaker accepts a POST but reverts
        self.fail_reads_after_post = False
        self.posted: dict = {}
        self.post_gate: asyncio.Event | None = None
        self.closed = False

    async def _read(self, name, value):
        self.calls.append(f"get_{name}")
        if name in self.read_errors:
            raise self.read_errors[name]
        if self.fail_reads_after_post and any(c.startswith("set_") for c in self.calls):
            raise DeviceConnectionError("192.168.1.100", "gone")
        return value

    async def get_language(self):
        return await self._read("language", self.language)

    async def get_clock(self):
        return await self._read("clock", self.clock)

    async def get_power_saving(self):
        return await self._read("power_saving", self.power)

    async def _post(self, name):
        self.calls.append(f"set_{name}")
        if self.post_gate is not None:
            await self.post_gate.wait()
        if self.post_error:
            raise self.post_error

    async def set_language(self, language_id):
        await self._post("language")
        self.posted["language"] = language_id
        if not self.keep_old_value:
            self.language = LanguageSetting(language_id, LANGUAGES.get(language_id))

    async def set_clock(self, enabled, time_format, timezone, extra):
        await self._post("clock")
        self.posted["clock"] = (enabled, time_format, timezone, dict(extra))
        if not self.keep_old_value:
            self.clock = ClockSetting(enabled, time_format, timezone, dict(extra))

    async def set_power_saving(self, enabled):
        await self._post("power_saving")
        self.posted["power_saving"] = enabled
        if not self.keep_old_value:
            self.power = PowerSavingSetting(enabled)

    async def close(self):
        self.closed = True


@pytest.fixture
def client():
    return FakeSettingsClient()


@pytest.fixture
def service(client):
    repository = AsyncMock()
    repository.get_by_device_id.return_value = Device(
        device_id="AABB",
        ip="192.168.1.100",
        name="Kitchen",
        model="SoundTouch 10",
        mac_address="AABB",
        firmware_version="1.0",
    )
    svc = DeviceService(
        repository=repository, sync_service=AsyncMock(), discovery_adapter=AsyncMock()
    )
    with patch("opencloudtouch.devices.service.get_device_client", return_value=client):
        yield svc


class TestRead:
    @pytest.mark.asyncio
    async def test_returns_all_three_settings_and_availability(self, service):
        result = await service.get_device_settings("AABB")

        assert result.language == LanguageSetting(2, "Deutsch")
        assert result.clock.time_format == "24h"
        assert result.power_saving == PowerSavingSetting(False)
        assert result.available == {
            "language": True,
            "clock": True,
            "power_saving": True,
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            None,  # getter returns None
            ValueError("bad xml"),
            NotImplementedError(),
            TimeoutError(),
        ],
    )
    async def test_one_failing_setting_is_just_unavailable(
        self, service, client, error
    ):
        if error is None:
            client.clock = None
        else:
            client.read_errors["clock"] = error

        result = await service.get_device_settings("AABB")

        assert result.clock is None
        assert result.available == {
            "language": True,
            "clock": False,
            "power_saving": True,
        }
        assert result.language is not None

    @pytest.mark.asyncio
    async def test_slow_setting_times_out_without_failing_the_request(
        self, service, client
    ):
        async def slow():
            await asyncio.sleep(10)

        client.get_clock = slow
        with patch("opencloudtouch.devices.service._SETTING_READ_TIMEOUT", 0.05):
            result = await service.get_device_settings("AABB")
        assert result.clock is None
        assert result.available["clock"] is False

    @pytest.mark.asyncio
    async def test_connection_error_on_some_reads_only_hides_those(
        self, service, client
    ):
        client.read_errors["language"] = DeviceConnectionError("1.2.3.4", "refused")
        result = await service.get_device_settings("AABB")
        assert result.language is None
        assert result.clock is not None

    @pytest.mark.asyncio
    async def test_unreachable_on_all_reads_raises_device_connection_error(
        self, service, client
    ):
        for name in ("language", "clock", "power_saving"):
            client.read_errors[name] = DeviceConnectionError("1.2.3.4", "refused")
        with pytest.raises(DeviceConnectionError):
            await service.get_device_settings("AABB")

    @pytest.mark.asyncio
    async def test_unknown_device(self, service):
        service.repository.get_by_device_id.return_value = None
        with pytest.raises(DeviceNotFoundError):
            await service.get_device_settings("nope")

    @pytest.mark.asyncio
    async def test_client_is_closed(self, service, client):
        await service.get_device_settings("AABB")
        assert client.closed


class TestWriteLanguage:
    @pytest.mark.asyncio
    async def test_sequence_is_pre_read_post_post_read(self, service, client):
        result = await service.set_device_language("AABB", 12)

        assert client.calls == ["get_language", "set_language", "get_language"]
        assert client.posted["language"] == 12
        assert result.applied is True
        assert result.value == LanguageSetting(12, "한국어")

    @pytest.mark.asyncio
    async def test_speaker_reverting_gives_applied_false_with_real_value(
        self, service, client
    ):
        client.keep_old_value = True
        result = await service.set_device_language("AABB", 12)
        assert result.applied is False
        assert result.value == LanguageSetting(2, "Deutsch")

    @pytest.mark.asyncio
    async def test_failing_post_read_gives_applied_false_and_no_value(
        self, service, client
    ):
        client.fail_reads_after_post = True
        result = await service.set_device_language("AABB", 12)
        assert result.applied is False
        assert result.value is None

    @pytest.mark.asyncio
    async def test_unknown_id_reported_by_speaker_has_no_name(self, service, client):
        client.language = LanguageSetting(99, None)
        result = await service.get_device_settings("AABB")
        assert result.language == LanguageSetting(99, None)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, 14, 26, -1, "x", "3", 3.5, True, None])
    async def test_invalid_id_is_rejected_before_any_device_call(
        self, service, client, bad
    ):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_device_language("AABB", bad)
        assert excinfo.value.status_code == 422
        assert excinfo.value.code == "settings_language_invalid"
        assert excinfo.value.field == "language_id"
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_unavailable_setting_gives_409_without_post(self, service, client):
        client.language = None
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_device_language("AABB", 3)
        assert excinfo.value.status_code == 409
        assert excinfo.value.code == "setting_not_available"
        assert client.calls == ["get_language"]


class TestWriteClock:
    @pytest.mark.asyncio
    async def test_enabled_write_keeps_extra_attributes(self, service, client):
        result = await service.set_device_clock("AABB", True, "12h", "Asia/Tokyo")

        enabled, time_format, timezone, extra = client.posted["clock"]
        assert (enabled, time_format, timezone) == (True, "12h", "Asia/Tokyo")
        assert extra == {
            "userOffsetMinute": "0",
            "userUtcTime": "0",
            "brightnessLevel": "3",
        }
        assert client.calls == ["get_clock", "set_clock", "get_clock"]
        assert result.applied is True
        assert result.value.timezone == "Asia/Tokyo"

    @pytest.mark.asyncio
    async def test_disabling_resends_the_values_read_and_ignores_the_request_fields(
        self, service, client
    ):
        result = await service.set_device_clock("AABB", False, "bogus", "Not/AZone")

        enabled, time_format, timezone, extra = client.posted["clock"]
        assert enabled is False
        assert (time_format, timezone) == ("24h", "Europe/Berlin")
        assert extra["brightnessLevel"] == "3"
        assert result.applied is True

    @pytest.mark.asyncio
    async def test_applied_false_when_timezone_differs_case_sensitively(
        self, service, client
    ):
        original = client.set_clock

        async def lowercase_zone(enabled, time_format, timezone, extra):
            await original(enabled, time_format, timezone.lower(), extra)

        client.set_clock = lowercase_zone
        result = await service.set_device_clock("AABB", True, "24h", "Europe/Berlin")
        assert result.applied is False
        assert result.value.timezone == "europe/berlin"

    @pytest.mark.asyncio
    async def test_applied_false_when_format_not_kept(self, service, client):
        original = client.set_clock

        async def ignore_format(enabled, time_format, timezone, extra):
            await original(enabled, "24h", timezone, extra)

        client.set_clock = ignore_format
        result = await service.set_device_clock("AABB", True, "12h", "Europe/Berlin")
        assert result.applied is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("args", "code", "field"),
        [
            (("yes", "24h", "UTC"), "settings_enabled_invalid", "enabled"),
            ((None, "24h", "UTC"), "settings_enabled_invalid", "enabled"),
            ((1, "24h", "UTC"), "settings_enabled_invalid", "enabled"),
            ((True, "13h", "UTC"), "settings_time_format_invalid", "time_format"),
            ((True, None, "UTC"), "settings_time_format_invalid", "time_format"),
            ((True, "24H", "UTC"), "settings_time_format_invalid", "time_format"),
            ((True, "24h", "Europe/Atlantis"), "settings_timezone_invalid", "timezone"),
            ((True, "24h", ""), "settings_timezone_invalid", "timezone"),
            ((True, "24h", None), "settings_timezone_invalid", "timezone"),
            ((True, "24h", "x" * 65), "settings_timezone_invalid", "timezone"),
            ((True, "24h", "CET-1CEST"), "settings_timezone_invalid", "timezone"),
            ((True, "24h", "Factory"), "settings_timezone_invalid", "timezone"),
            ((True, "24h", 'Europe/"Berlin'), "settings_timezone_invalid", "timezone"),
            ((True, "24h", "Europe/<Berlin"), "settings_timezone_invalid", "timezone"),
        ],
    )
    async def test_validation(self, service, client, args, code, field):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_device_clock("AABB", *args)
        assert excinfo.value.status_code == 422
        assert excinfo.value.code == code
        assert excinfo.value.field == field
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_first_violation_wins_in_body_order(self, service):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_device_clock("AABB", True, "13h", "Nope")
        assert excinfo.value.code == "settings_time_format_invalid"

    @pytest.mark.asyncio
    async def test_unavailable_clock_gives_409_without_post(self, service, client):
        client.clock = None
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_device_clock("AABB", True, "24h", "UTC")
        assert excinfo.value.code == "setting_not_available"
        assert "set_clock" not in client.calls


class TestWritePowerSaving:
    @pytest.mark.asyncio
    async def test_sequence_and_result(self, service, client):
        result = await service.set_device_power_saving("AABB", True)

        assert client.calls == [
            "get_power_saving",
            "set_power_saving",
            "get_power_saving",
        ]
        assert client.posted["power_saving"] is True
        assert result.applied is True
        assert result.value == PowerSavingSetting(True)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["true", 1, None])
    async def test_non_boolean_is_rejected(self, service, client, bad):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_device_power_saving("AABB", bad)
        assert excinfo.value.code == "settings_enabled_invalid"
        assert client.calls == []


class TestErrorsAndConcurrency:
    @pytest.mark.asyncio
    async def test_http_error_from_speaker_is_device_rejected(self, service, client):
        client.post_error = DeviceRejectedError("192.168.1.100", 500)
        with pytest.raises(DeviceRejectedError):
            await service.set_device_language("AABB", 3)

    @pytest.mark.asyncio
    async def test_unreachable_speaker_on_pre_read_raises_connection_error(
        self, service, client
    ):
        client.read_errors["language"] = DeviceConnectionError("1.2.3.4", "refused")
        with pytest.raises(DeviceConnectionError):
            await service.set_device_language("AABB", 3)
        assert "set_language" not in client.calls

    @pytest.mark.asyncio
    async def test_unknown_device(self, service):
        service.repository.get_by_device_id.return_value = None
        with pytest.raises(DeviceNotFoundError):
            await service.set_device_power_saving("nope", True)

    @pytest.mark.asyncio
    async def test_writes_for_one_device_run_one_after_the_other(self, service, client):
        client.post_gate = asyncio.Event()

        first = asyncio.create_task(service.set_device_language("AABB", 3))
        await asyncio.sleep(0.01)
        second = asyncio.create_task(service.set_device_power_saving("AABB", True))
        await asyncio.sleep(0.05)

        # the second write has not started its pre-read while the first holds the lock
        assert client.calls.count("get_power_saving") == 0
        client.post_gate.set()
        await asyncio.gather(first, second)
        assert client.calls.index("get_power_saving") > client.calls.index(
            "set_language"
        )

    @pytest.mark.asyncio
    async def test_reads_do_not_wait_for_the_write_lock(self, service, client):
        client.post_gate = asyncio.Event()
        write = asyncio.create_task(service.set_device_language("AABB", 3))
        await asyncio.sleep(0.01)

        result = await asyncio.wait_for(service.get_device_settings("AABB"), timeout=1)

        assert result.language is not None
        client.post_gate.set()
        await write

    @pytest.mark.asyncio
    async def test_locks_are_per_device_and_created_lazily(self, service):
        assert service._setting_locks == {}
        await service.set_device_power_saving("AABB", True)
        assert list(service._setting_locks) == ["AABB"]
