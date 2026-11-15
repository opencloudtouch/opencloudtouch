"""Every action that is sent to a speaker answers 503 ``device_unreachable`` when it is offline.

The action is not carried out and nothing is changed in OCT, so the caller can simply
try again once the speaker is back.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import (
    get_device_service,
    get_device_state_manager,
    get_preset_service,
)
from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.main import app

DEV = "AABBCCDDEEFF"
OFFLINE = DeviceConnectionError("10.0.0.1", "offline")

PRESET_BODY = {
    "device_id": DEV,
    "preset_number": 1,
    "station_uuid": "u",
    "station_name": "Station",
    "station_url": "http://stream.example.org/live",
}

# (method, url, json body) of every action that talks to the speaker
ACTIONS = [
    ("put", f"/api/devices/{DEV}/volume", {"level": 5}),
    ("put", f"/api/devices/{DEV}/mute", {"muted": True}),
    ("put", f"/api/devices/{DEV}/source", {"source": "AUX"}),
    ("post", f"/api/devices/{DEV}/key?key=PLAY", None),
    ("put", f"/api/devices/{DEV}/settings/bass", {"level": 1}),
    ("post", f"/api/devices/{DEV}/reboot", None),
    ("put", f"/api/devices/{DEV}/name", {"name": "New"}),
    ("post", "/api/presets/set", PRESET_BODY),
    ("delete", f"/api/presets/{DEV}/1", None),
    ("delete", f"/api/presets/{DEV}", None),
    ("post", f"/api/presets/{DEV}/sync", None),
]


@pytest.fixture
def offline_speaker():
    device_service = MagicMock()
    for name in (
        "set_volume",
        "set_mute",
        "select_source",
        "press_key",
        "set_device_bass",
        "reboot_device",
    ):
        setattr(device_service, name, AsyncMock(side_effect=OFFLINE))

    @asynccontextmanager
    async def client_that_is_offline(_device_id):
        client = AsyncMock()
        client.set_name.side_effect = OFFLINE
        yield client

    device_service.get_device_by_id = AsyncMock(return_value=MagicMock(name="Old"))
    device_service._device_client = client_that_is_offline
    device_service.repository.upsert = AsyncMock()

    preset_service = MagicMock()
    for name in (
        "set_preset",
        "clear_preset",
        "clear_all_presets",
        "sync_presets_from_device",
    ):
        setattr(preset_service, name, AsyncMock(side_effect=OFFLINE))

    app.dependency_overrides[get_device_service] = lambda: device_service
    app.dependency_overrides[get_preset_service] = lambda: preset_service
    app.dependency_overrides[get_device_state_manager] = lambda: AsyncMock()
    yield device_service
    for dep in (get_device_service, get_preset_service, get_device_state_manager):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.parametrize("method,url,body", ACTIONS)
def test_offline_speaker_answers_503_device_unreachable(
    offline_speaker, method, url, body
):
    kwargs = {"json": body} if body is not None else {}
    response = getattr(TestClient(app), method)(url, **kwargs)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "device_unreachable"


@pytest.mark.parametrize("method,url,body", ACTIONS)
def test_offline_error_text_is_fixed_and_has_no_ip_or_library_text(
    offline_speaker, method, url, body
):
    kwargs = {"json": body} if body is not None else {}
    response = getattr(TestClient(app), method)(url, **kwargs)

    detail = response.json()["detail"]
    assert "10.0.0.1" not in detail
    assert "offline" not in detail
    assert detail == (
        "The device did not respond. The action was not carried out; "
        "try again when it is back online."
    )


def test_failed_rename_does_not_touch_the_oct_database(offline_speaker):
    TestClient(app).put(f"/api/devices/{DEV}/name", json={"name": "New"})

    offline_speaker.repository.upsert.assert_not_awaited()
