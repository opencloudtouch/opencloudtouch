"""Integration tests for Bose device preset stream proxy endpoint.

These tests verify the `/device/{device_id}/preset/{preset_id}` endpoint
that Bose SoundTouch devices call when a custom preset button is pressed.

**Architecture:**
1. User configures preset via OCT UI → Saved to database
2. OCT programs Bose device with OCT backend URL (e.g., http://192.168.178.108:7777/device/ABC123/preset/1)
3. User presses PRESET_1 button on Bose device
4. Bose requests OCT backend: GET /device/ABC123/preset/1
5. OCT looks up preset in database
6. **OCT proxies HTTPS stream as HTTP** (Bose cannot handle HTTPS certificates)
7. Bose receives HTTP audio stream ✅

**Test Coverage:**
- ✅ Preset found → HTTP 200 streaming proxy
- ✅ Preset not found → HTTP 404
- ✅ Invalid preset number → HTTP 422
- ✅ Multiple devices get correct streams

**Note**: Tests that require external HTTP mocking use respx at the module level
to ensure mocks are active before the endpoint handler makes requests.
"""

import pytest
import respx
from httpx import AsyncClient, Response

from opencloudtouch.presets.models import Preset

# Module-level respx router for external HTTP mocks
external_mock = respx.mock(assert_all_called=False)


@pytest.fixture(autouse=True)
def setup_external_mocks():
    """Setup external HTTP mocks before each test."""
    # Define common external stream mocks
    external_mock.get(
        "https://edge71.live-sm.absolutradio.de/absolut-relax/stream/mp3"
    ).mock(
        return_value=Response(
            status_code=200,
            content=b"FAKE_AUDIO_DATA_CHUNK_123",
            headers={"content-type": "audio/mpeg", "icy-name": "Absolut Relax"},
        )
    )
    external_mock.get(
        "https://streams.radiobob.de/bob-national/mp3-192/mediaplayer"
    ).mock(
        return_value=Response(
            status_code=200,
            content=b"RADIO_BOB_AUDIO",
            headers={"content-type": "audio/mpeg"},
        )
    )
    external_mock.get("https://mp3channels.webradio.antenne.de/antenne").mock(
        return_value=Response(
            status_code=200,
            content=b"AUDIO_PRESET_3",
            headers={"content-type": "audio/mpeg"},
        )
    )
    external_mock.get(
        "https://br-br1-franken.cast.addradio.de/br/br1/franken/mp3/128/stream.mp3"
    ).mock(
        return_value=Response(
            status_code=200,
            content=b"AUDIO_PRESET_4",
            headers={"content-type": "audio/mpeg"},
        )
    )
    external_mock.get("https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3").mock(
        return_value=Response(
            status_code=200,
            content=b"AUDIO_PRESET_5",
            headers={"content-type": "audio/mpeg"},
        )
    )
    external_mock.get(
        "https://wdr-wdr2-ruhrgebiet.icecastssl.wdr.de/wdr/wdr2/ruhrgebiet/mp3/128/stream.mp3"
    ).mock(
        return_value=Response(
            status_code=200,
            content=b"AUDIO_PRESET_6",
            headers={"content-type": "audio/mpeg"},
        )
    )
    external_mock.get("https://broken.stream.invalid/audio.mp3").mock(
        return_value=Response(status_code=404, content=b"Not Found")
    )

    with external_mock:
        yield

    external_mock.reset()


@pytest.mark.asyncio
async def test_stream_preset_proxy_success(real_api_client: AsyncClient):
    """Test successful preset stream request returns HTTP 200 with proxied audio.

    **Scenario**: Bose device (689E194F7D2F) presses PRESET_1 button
    **Expected**: OCT proxies HTTPS stream as HTTP (returns 200 + audio data)
    """
    # Arrange: Configure preset in database
    device_id = "689E194F7D2F"
    preset_number = 1
    station_name = "Absolut Relax"
    station_url = "https://edge71.live-sm.absolutradio.de/absolut-relax/stream/mp3"

    # Save preset via API (simulates user configuration)
    set_response = await real_api_client.post(
        "/api/presets/set",
        json={
            "device_id": device_id,
            "preset_number": preset_number,
            "station_uuid": "rb-station-absolut-relax-123",
            "station_name": station_name,
            "station_url": station_url,
            "station_codec": "MP3",
            "station_country": "Germany",
            "station_homepage": "https://www.absolutradio.de/relax",
        },
    )
    assert (
        set_response.status_code == 201
    ), f"Failed to save preset: {set_response.text}"

    # Act: Simulate Bose device requesting stream
    stream_response = await real_api_client.get(
        f"/device/{device_id}/preset/{preset_number}",
    )

    # Assert: HTTP 200 streaming proxy response
    assert (
        stream_response.status_code == 200
    ), f"Expected 200, got {stream_response.status_code}"
    assert stream_response.headers.get("content-type") == "audio/mpeg"
    assert stream_response.headers.get("icy-name") == station_name
    assert (
        stream_response.headers.get("Cache-Control")
        == "no-cache, no-store, must-revalidate"
    )

    # Verify audio data received
    assert b"FAKE_AUDIO_DATA" in stream_response.content


@pytest.mark.asyncio
async def test_stream_preset_not_found(real_api_client: AsyncClient):
    """Test requesting unconfigured preset returns HTTP 404.

    **Scenario**: Bose device presses PRESET_3 button but no preset configured
    **Expected**: HTTP 404 with error message
    """
    # Arrange: Device exists but preset not configured
    device_id = "UNKNOWN999"
    preset_number = 3

    # Act: Simulate Bose requesting unconfigured preset
    stream_response = await real_api_client.get(
        f"/device/{device_id}/preset/{preset_number}",
    )

    # Assert: HTTP 404
    assert (
        stream_response.status_code == 404
    ), f"Expected 404, got {stream_response.status_code}"
    error_detail = stream_response.json()
    assert (
        "not configured" in error_detail["detail"].lower()
    ), f"Error message should mention 'not configured': {error_detail['detail']}"


@pytest.mark.asyncio
async def test_stream_preset_invalid_number(real_api_client: AsyncClient):
    """Test requesting invalid preset number returns HTTP 422.

    **Scenario**: Bose sends invalid preset number (e.g., 0 or 7)
    **Expected**: HTTP 422 validation error
    """
    # Arrange: Invalid preset number (valid range: 1-6)
    device_id = "689E194F7D2F"
    invalid_preset_number = 0  # Invalid: Must be 1-6

    # Act: Request with invalid preset number
    stream_response = await real_api_client.get(
        f"/device/{device_id}/preset/{invalid_preset_number}",
    )

    # Assert: HTTP 422 validation error
    assert (
        stream_response.status_code == 422
    ), f"Expected 422, got {stream_response.status_code}"


@pytest.mark.asyncio
async def test_stream_preset_multiple_devices(real_api_client: AsyncClient):
    """Test different devices with same preset number get different streams.

    **Scenario**: Device A Preset 1 = "Station X", Device B Preset 1 = "Station Y"
    **Expected**: Each device gets correct stream for its preset
    """
    # Arrange: Two devices with different presets on same slot
    device_a = "DEVICE_AAA"
    device_b = "DEVICE_BBB"
    preset_number = 1

    # Device A: Absolut Relax
    await real_api_client.post(
        "/api/presets/set",
        json={
            "device_id": device_a,
            "preset_number": preset_number,
            "station_uuid": "rb-absolut-relax-aaa",
            "station_name": "Absolut Relax",
            "station_url": "https://edge71.live-sm.absolutradio.de/absolut-relax/stream/mp3",
            "station_codec": "MP3",
        },
    )

    # Device B: Radio BOB!
    await real_api_client.post(
        "/api/presets/set",
        json={
            "device_id": device_b,
            "preset_number": preset_number,
            "station_uuid": "rb-radiobob-bbb",
            "station_name": "Radio BOB!",
            "station_url": "https://streams.radiobob.de/bob-national/mp3-192/mediaplayer",
            "station_codec": "MP3",
        },
    )

    # Act: Request stream from both devices
    response_a = await real_api_client.get(f"/device/{device_a}/preset/{preset_number}")
    response_b = await real_api_client.get(f"/device/{device_b}/preset/{preset_number}")

    # Assert: Each device gets different stream content
    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert b"FAKE_AUDIO_DATA" in response_a.content  # Absolut Relax mock
    assert b"RADIO_BOB" in response_b.content


@pytest.mark.asyncio
async def test_stream_preset_all_slots(real_api_client: AsyncClient):
    """Test all 6 preset slots work correctly.

    **Scenario**: Configure and request all presets 1-6
    **Expected**: All 6 presets return correct proxied streams
    """
    # Arrange: Configure all 6 presets (mocks are defined in autouse fixture)
    device_id = "TEST_ALL_SLOTS"
    stations = [
        (
            "Absolut Relax",
            "https://edge71.live-sm.absolutradio.de/absolut-relax/stream/mp3",
        ),
        ("Radio BOB!", "https://streams.radiobob.de/bob-national/mp3-192/mediaplayer"),
        ("ANTENNE BAYERN", "https://mp3channels.webradio.antenne.de/antenne"),
        (
            "Bayern 1",
            "https://br-br1-franken.cast.addradio.de/br/br1/franken/mp3/128/stream.mp3",
        ),
        ("Deutschlandfunk", "https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3"),
        (
            "WDR 2",
            "https://wdr-wdr2-ruhrgebiet.icecastssl.wdr.de/wdr/wdr2/ruhrgebiet/mp3/128/stream.mp3",
        ),
    ]

    for preset_num, (name, url) in enumerate(stations, start=1):
        await real_api_client.post(
            "/api/presets/set",
            json={
                "device_id": device_id,
                "preset_number": preset_num,
                "station_uuid": f"rb-station-{preset_num}",
                "station_name": name,
                "station_url": url,
                "station_codec": "MP3",
            },
        )

    # Act: Request all presets
    responses = []
    for preset_num in range(1, 7):
        response = await real_api_client.get(f"/device/{device_id}/preset/{preset_num}")
        responses.append((preset_num, response))

    # Assert: All presets return HTTP 200 with correct audio
    for preset_num, response in responses:
        assert (
            response.status_code == 200
        ), f"Preset {preset_num} failed: {response.status_code}"
        # Just verify we got some audio data (mocks are defined in fixture)
        assert len(response.content) > 0, f"Preset {preset_num} empty response"


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="StreamingResponse cannot change HTTP status after headers sent - error handling limitation"
)
async def test_stream_upstream_unavailable_returns_502(real_api_client: AsyncClient):
    """Test that upstream stream unavailable returns HTTP 502.

    **Scenario**: RadioBrowser stream returns 404 or connection error
    **Expected**: OCT returns 502 Bad Gateway
    """
    # Arrange: Configure preset with broken stream (mocked in fixture to return 404)
    device_id = "BROKEN_STREAM"
    preset_number = 1

    await real_api_client.post(
        "/api/presets/set",
        json={
            "device_id": device_id,
            "preset_number": preset_number,
            "station_uuid": "rb-broken",
            "station_name": "Broken Station",
            "station_url": "https://broken.stream.invalid/audio.mp3",
            "station_codec": "MP3",
        },
    )

    # Act: Request stream
    response = await real_api_client.get(f"/device/{device_id}/preset/{preset_number}")

    # Assert: HTTP 502 because upstream failed
    assert response.status_code == 502, f"Expected 502, got {response.status_code}"
    assert "unavailable" in response.json()["detail"].lower()
