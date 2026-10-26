"""Sleep timer endpoints and the stateful mock device end to end."""

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from opencloudtouch.core.dependencies import get_sleep_timer_service
from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.main import app
from opencloudtouch.sleep_timer.service import SleepTimerService
from tests.unit.helpers.fake_playback import unreachable
from tests.unit.sleep_timer.conftest import DEVICE, drain

URL = f"/api/devices/{DEVICE}/sleep-timer"


@pytest_asyncio.fixture
async def client(service):
    """Async client: requests and the timer task share one event loop."""
    app.dependency_overrides[get_sleep_timer_service] = lambda: service
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


class TestGet:
    @pytest.mark.asyncio
    async def test_inactive_by_default(self, client):
        response = await client.get(URL)
        assert response.status_code == 200
        body = response.json()
        assert body["active"] is False
        assert body["server_time"].endswith("Z")
        assert body["ends_at"] is None
        assert body["state"] is None

    @pytest.mark.asyncio
    async def test_unknown_device(self, client, devices):
        devices.missing = True
        response = await client.get(URL)
        assert response.status_code == 404
        assert response.json()["code"] == "device_not_found"

    @pytest.mark.asyncio
    async def test_makes_no_device_call(self, client, devices):
        await client.put(URL, json={"duration_minutes": 5, "fade_seconds": 0})
        before = len(devices.calls)
        await client.get(URL)
        assert len(devices.calls) == before


class TestPut:
    @pytest.mark.asyncio
    async def test_starts_a_timer_with_defaults(self, client, vtime):
        response = await client.put(URL, json={"duration_minutes": 30})
        assert response.status_code == 200
        body = response.json()
        assert body["active"] is True
        assert body["device_id"] == DEVICE
        assert body["duration_minutes"] == 30
        assert body["fade_seconds"] == 30
        assert body["end_action"] == "stop"
        assert body["state"] == "running"
        assert body["ends_at"] > body["server_time"]

    @pytest.mark.asyncio
    async def test_get_returns_the_same_timer(self, client):
        put = (
            await client.put(URL, json={"duration_minutes": 5, "fade_seconds": 0})
        ).json()
        got = (await client.get(URL)).json()
        assert got["ends_at"] == put["ends_at"]
        assert got["active"] is True

    @pytest.mark.asyncio
    async def test_fade_longer_than_the_duration(self, client):
        response = await client.put(
            URL, json={"duration_minutes": 1, "fade_seconds": 61}
        )
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "sleep_timer_fade_too_long"
        assert body["errors"][0]["path"] == "fade_seconds"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"duration_minutes": 0},
            {"duration_minutes": 721},
            {"duration_minutes": "x"},
            {"duration_minutes": 5, "fade_seconds": -1},
            {"duration_minutes": 5, "fade_seconds": 301},
            {"duration_minutes": 5, "end_action": "explode"},
        ],
    )
    async def test_invalid_values_are_validation_errors(self, client, body):
        response = await client.put(URL, json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"

    @pytest.mark.asyncio
    async def test_unknown_device(self, client, devices):
        devices.missing = True
        response = await client.put(URL, json={"duration_minutes": 5})
        assert response.status_code == 404
        assert response.json()["code"] == "device_not_found"

    @pytest.mark.asyncio
    async def test_unreachable_device(self, client, devices):
        devices.fail("get_volume", unreachable())
        response = await client.put(URL, json={"duration_minutes": 5})
        assert response.status_code == 503
        assert response.json()["code"] == "device_unreachable"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["stop", "standby"])
    async def test_end_actions(self, client, action):
        response = await client.put(
            URL, json={"duration_minutes": 5, "fade_seconds": 0, "end_action": action}
        )
        assert response.json()["end_action"] == action


class TestStates:
    @pytest.mark.asyncio
    async def test_running_fading_ending(self, client, service, vtime, devices):
        await client.put(URL, json={"duration_minutes": 10, "fade_seconds": 30})
        assert (await client.get(URL)).json()["state"] == "running"

        await vtime.advance(10 * 60 - 20)
        assert (await client.get(URL)).json()["state"] == "fading"

        # hold the end sequence open: it only sleeps after the pause press
        await vtime.advance(25)
        body = (await client.get(URL)).json()
        assert body["state"] in ("ending", None) or body["active"] is False
        await drain(service)

    @pytest.mark.asyncio
    async def test_ending_while_the_end_sequence_runs(
        self, client, service, vtime, devices
    ):
        await client.put(URL, json={"duration_minutes": 1, "fade_seconds": 0})
        await vtime.advance(61)  # now inside stop_playback's 2 s settle
        body = (await client.get(URL)).json()
        assert body["active"] is True
        assert body["state"] == "ending"
        await vtime.advance(5)
        await drain(service)
        assert (await client.get(URL)).json()["active"] is False


class TestDelete:
    @pytest.mark.asyncio
    async def test_cancels_and_is_idempotent(self, client, service):
        await client.put(URL, json={"duration_minutes": 5, "fade_seconds": 0})
        first = await client.delete(URL)
        second = await client.delete(URL)
        assert first.status_code == 204
        assert second.status_code == 204
        assert (await client.get(URL)).json()["active"] is False

    @pytest.mark.asyncio
    async def test_restores_the_faded_volume(self, client, vtime, devices):
        devices.volume = 40
        await client.put(URL, json={"duration_minutes": 30, "fade_seconds": 30})
        await vtime.advance(30 * 60 - 15)
        assert devices.volume < 40
        assert (await client.delete(URL)).status_code == 204
        assert devices.volume == 40


class TestMockMode:
    """Start -> fade -> pause is observable through the real DeviceService + mock."""

    @pytest.mark.asyncio
    async def test_timer_against_the_stateful_mock_device(
        self, monkeypatch, vtime, repository
    ):
        monkeypatch.setenv("OCT_MOCK_MODE", "true")
        device_repo = AsyncMock()
        device_repo.get_by_device_id.side_effect = lambda device_id: (
            Device(
                device_id=DEVICE,
                ip="192.168.1.100",
                name="Living Room",
                model="SoundTouch 20",
                mac_address=DEVICE,
                firmware_version="1.0",
            )
            if device_id == DEVICE
            else None
        )
        device_service = DeviceService(
            repository=device_repo,
            sync_service=AsyncMock(),
            discovery_adapter=AsyncMock(),
        )
        timers = SleepTimerService(
            device_service=device_service,
            repository=repository,
            clock=vtime.clock,
            sleep=vtime.sleep,
        )

        await device_service.set_volume(DEVICE, 40)
        await timers.start(DEVICE, 30, 30, "stop")
        vtime.jump(30 * 60 - 40)  # fast-forward the countdown (clock only)

        # The mock client is created in a worker thread, so give real time per step.
        async def pump(seconds: int) -> None:
            for _ in range(seconds):
                await vtime.advance(1)
                await asyncio.sleep(0.02)

        await pump(25)  # t = end - 15 s: inside the fade
        mid = await device_service.get_volume(DEVICE)
        assert 0 < mid.actual < 40  # visible through the service

        await pump(25)
        await drain(timers)
        assert (await device_service.get_volume(DEVICE)).actual == 40
        assert (await device_service.get_now_playing(DEVICE)).state == "PAUSE_STATE"
