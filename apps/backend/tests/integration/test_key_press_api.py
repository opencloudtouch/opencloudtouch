"""
Integration tests for /api/devices/{device_id}/key endpoint (Iteration 4).

Tests key press endpoint with mock devices.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.main import app


@pytest.mark.asyncio
async def test_press_preset_key_success():
    """Test successful preset key press via API."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.press_key = AsyncMock()

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/devices/AABBCC112233/key",
                params={"key": "PRESET_1", "state": "both"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Key PRESET_1 pressed successfully"
        assert data["device_id"] == "AABBCC112233"

        # Verify press_key was called
        mock_service.press_key.assert_called_once_with(
            "AABBCC112233", "PRESET_1", "both"
        )

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_press_key_device_not_found():
    """Test key press for non-existent device."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.core.exceptions import DeviceNotFoundError
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService that raises DeviceNotFoundError
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.press_key = AsyncMock(side_effect=DeviceNotFoundError("NONEXISTENT"))

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/devices/NONEXISTENT/key",
                params={"key": "PRESET_1", "state": "both"},
            )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_press_key_invalid_key():
    """Test key press with invalid key name."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.core.exceptions import DomainValidationError
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService that raises DomainValidationError for invalid key
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.press_key = AsyncMock(
        side_effect=DomainValidationError("Invalid key: INVALID_KEY", field="key")
    )

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/devices/AABBCC112233/key",
                params={"key": "INVALID_KEY", "state": "both"},
            )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid key" in data["detail"]

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_press_key_all_states():
    """Test all key states: press, release, both."""
    from opencloudtouch.core.dependencies import get_device_service
    from opencloudtouch.devices.service import DeviceService

    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.press_key = AsyncMock()

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test press
            response = await client.post(
                "/api/devices/AABBCC112233/key",
                params={"key": "PRESET_1", "state": "press"},
            )
            assert response.status_code == 200

            # Test release
            response = await client.post(
                "/api/devices/AABBCC112233/key",
                params={"key": "PRESET_1", "state": "release"},
            )
            assert response.status_code == 200

            # Test both
            response = await client.post(
                "/api/devices/AABBCC112233/key",
                params={"key": "PRESET_1", "state": "both"},
            )
            assert response.status_code == 200

        # Verify all three calls were made
        assert mock_service.press_key.call_count == 3

    finally:
        app.dependency_overrides.clear()


def _service_with_settings(shuffle="SHUFFLE_ON", repeat="REPEAT_ALL"):
    from opencloudtouch.devices.client import NowPlayingInfo
    from opencloudtouch.devices.service import DeviceService

    svc = AsyncMock(spec=DeviceService)
    svc.get_now_playing = AsyncMock(
        return_value=NowPlayingInfo(
            source="STORED_MUSIC",
            state="PLAY_STATE",
            shuffle_setting=shuffle,
            repeat_setting=repeat,
        )
    )
    return svc


async def _post_key(svc, params):
    from opencloudtouch.core.dependencies import get_device_service

    app.dependency_overrides[get_device_service] = lambda: svc
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/api/devices/AABBCC112233/key", params=params)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["both", "press", "release"])
async def test_key_shuffle_on_returns_read_back_settings(state):
    svc = _service_with_settings()

    response = await _post_key(svc, {"key": "SHUFFLE_ON", "state": state})

    assert response.status_code == 200
    assert response.json() == {
        "message": "Key SHUFFLE_ON pressed successfully",
        "device_id": "AABBCC112233",
        "shuffle_setting": "SHUFFLE_ON",
        "repeat_setting": "REPEAT_ALL",
    }
    svc.press_key.assert_called_once_with("AABBCC112233", "SHUFFLE_ON", "both")


@pytest.mark.asyncio
async def test_other_keys_unchanged():
    svc = _service_with_settings()

    response = await _post_key(svc, {"key": "PRESET_1", "state": "press"})

    assert set(response.json()) == {"message", "device_id"}
    svc.press_key.assert_called_once_with("AABBCC112233", "PRESET_1", "press")
    svc.get_now_playing.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_key_still_400():
    from opencloudtouch.core.exceptions import DomainValidationError

    svc = _service_with_settings()
    svc.press_key = AsyncMock(
        side_effect=DomainValidationError("Invalid key: SHUFFLE_MAYBE", field="key")
    )

    response = await _post_key(svc, {"key": "SHUFFLE_MAYBE"})

    assert response.status_code == 400
    svc.get_now_playing.assert_not_called()
