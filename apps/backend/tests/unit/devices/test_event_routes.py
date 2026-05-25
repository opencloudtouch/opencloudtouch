"""Tests for SSE device event stream endpoint."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.devices.api.event_routes import (
    _event_to_sse,
    _snapshot_to_sse,
    _stream_events,
)
from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.state import DeviceState, DeviceStateManager
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

# ---------------------------------------------------------------------------
# SSE formatting helpers
# ---------------------------------------------------------------------------


class TestEventToSSE:
    def test_volume_event(self):
        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(actual=42, target=42, muted=False),
        )
        sse = _event_to_sse(event)
        assert sse.startswith("event: volume\n")
        assert "data: " in sse
        assert sse.endswith("\n\n")

        data = json.loads(sse.split("data: ")[1].strip())
        assert data["device_id"] == "D1"
        assert data["actual"] == 42
        assert data["muted"] is False

    def test_now_playing_event(self):
        event = DeviceEvent(
            device_id="D2",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="RADIO", state="PLAY_STATE", track="Song"
            ),
        )
        sse = _event_to_sse(event)
        data = json.loads(sse.split("data: ")[1].strip())
        assert data["device_id"] == "D2"
        assert data["source"] == "RADIO"
        assert data["track"] == "Song"

    def test_event_without_payload(self):
        event = DeviceEvent(device_id="D3", event_type=EventType.PRESETS)
        sse = _event_to_sse(event)
        assert "event: presets\n" in sse
        data = json.loads(sse.split("data: ")[1].strip())
        assert data["device_id"] == "D3"

    def test_metadata_enriched_event(self):
        """metadata_enriched should format like now_playing with enriched type."""
        event = DeviceEvent(
            device_id="D4",
            event_type=EventType.METADATA_ENRICHED,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="WDR 2",
                artwork_url="https://cdn.example.com/logo.png",
                artist="ICY Artist",
                track="ICY Track",
            ),
        )
        sse = _event_to_sse(event)
        assert sse.startswith("event: metadata_enriched\n")
        assert sse.endswith("\n\n")

        data = json.loads(sse.split("data: ")[1].strip())
        assert data["device_id"] == "D4"
        assert data["source"] == "INTERNET_RADIO"
        assert data["artwork_url"] == "https://cdn.example.com/logo.png"
        assert data["artist"] == "ICY Artist"
        assert data["track"] == "ICY Track"


class TestSnapshotToSSE:
    def test_full_snapshot(self):
        state = DeviceState(
            device_id="D1",
            now_playing=NowPlayingInfo(source="AUX", state="PLAY_STATE"),
            volume=VolumeInfo(actual=50, target=50, muted=False),
        )
        sse = _snapshot_to_sse("D1", state)
        assert "event: now_playing\n" in sse
        assert "event: volume\n" in sse

    def test_partial_snapshot_volume_only(self):
        state = DeviceState(
            device_id="D1",
            volume=VolumeInfo(actual=30, target=30, muted=True),
        )
        sse = _snapshot_to_sse("D1", state)
        assert "event: volume\n" in sse
        assert "now_playing" not in sse

    def test_empty_snapshot(self):
        state = DeviceState(device_id="D1")
        sse = _snapshot_to_sse("D1", state)
        assert sse == ""


# ---------------------------------------------------------------------------
# SSE endpoint integration
# ---------------------------------------------------------------------------


@pytest.fixture
def state_manager():
    return DeviceStateManager()


@pytest.fixture
def mock_request():
    """Mock FastAPI Request that reports not disconnected."""
    req = MagicMock()
    req.is_disconnected = AsyncMock(return_value=False)
    return req


class TestSSEEndpoint:
    @pytest.mark.asyncio
    async def test_initial_snapshot_pushed(self, state_manager, mock_request):
        """On connect, existing device states should be pushed as SSE."""
        state_manager.update_volume("D1", VolumeInfo(25, 25, False))
        state_manager.update_now_playing(
            "D2",
            NowPlayingInfo(source="AUX", state="PLAY_STATE", track="Init"),
        )

        # Disconnect immediately on first check (after snapshot yielded)
        mock_request.is_disconnected = AsyncMock(return_value=True)

        messages = []
        async for msg in _stream_events(mock_request, state_manager):
            messages.append(msg)

        joined = "".join(messages)
        assert "event: volume" in joined
        assert "event: now_playing" in joined

    @pytest.mark.asyncio
    async def test_receives_published_event(self, state_manager, mock_request):
        """Events published after connect should be received via generator."""
        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(actual=99, target=99, muted=False),
        )

        call_count = 0

        async def disconnect_after_event():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        mock_request.is_disconnected = disconnect_after_event

        # Pre-load event into the queue that _stream_events will subscribe to
        # We need to inject after subscribe, so use on_event after generator starts
        async def feed_event():
            await asyncio.sleep(0.05)  # Let generator start
            await state_manager.on_event(event)

        asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(feed_event()))

        messages = []
        async for msg in _stream_events(mock_request, state_manager):
            messages.append(msg)
            if '"actual": 99' in msg:
                break

        joined = "".join(messages)
        assert '"actual": 99' in joined

    @pytest.mark.asyncio
    async def test_keepalive_on_timeout(self, state_manager, mock_request):
        """Keepalive comment should be sent when no events arrive."""
        from unittest.mock import patch

        call_count = 0

        async def disconnect_after_keepalive():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        mock_request.is_disconnected = disconnect_after_keepalive

        # Patch wait_for to raise TimeoutError immediately
        with patch(
            "opencloudtouch.devices.api.event_routes.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            messages = []
            async for msg in _stream_events(mock_request, state_manager):
                messages.append(msg)

        assert any(": keepalive" in m for m in messages)

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, state_manager, mock_request):
        """After generator exits, subscriber should be removed."""
        mock_request.is_disconnected = AsyncMock(return_value=True)

        messages = []
        async for msg in _stream_events(mock_request, state_manager):
            messages.append(msg)

        assert len(state_manager._subscribers) == 0

    @pytest.mark.asyncio
    async def test_multiple_concurrent_clients(self, state_manager):
        """Multiple generators should each get their own queue."""
        req1 = MagicMock()
        req1.is_disconnected = AsyncMock(return_value=True)
        req2 = MagicMock()
        req2.is_disconnected = AsyncMock(return_value=True)

        state_manager.update_volume("D1", VolumeInfo(10, 10, False))

        msgs1 = [m async for m in _stream_events(req1, state_manager)]
        msgs2 = [m async for m in _stream_events(req2, state_manager)]

        # Both should get the snapshot
        assert any("volume" in m for m in msgs1)
        assert any("volume" in m for m in msgs2)
        # Both cleaned up
        assert len(state_manager._subscribers) == 0


class TestSSEFormat:
    def test_sse_json_matches_api_format(self):
        """SSE JSON payload must match existing REST API response format."""
        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(actual=42, target=42, muted=True),
        )
        sse = _event_to_sse(event)
        data = json.loads(sse.split("data: ")[1].strip())

        # Must match GET /devices/{id}/volume format
        assert "actual" in data
        assert "target" in data
        assert "muted" in data
        assert "device_id" in data

    def test_now_playing_matches_api_format(self):
        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="BLUETOOTH",
                state="PLAY_STATE",
                station_name="Station",
                artist="Artist",
                track="Track",
                album="Album",
                artwork_url="http://img.jpg",
            ),
        )
        sse = _event_to_sse(event)
        data = json.loads(sse.split("data: ")[1].strip())

        # Must match GET /devices/{id}/now-playing format
        for key in [
            "source",
            "state",
            "station_name",
            "artist",
            "track",
            "album",
            "artwork_url",
        ]:
            assert key in data


# ---------------------------------------------------------------------------
# Integration test: WS event → state manager → SSE → client receives
# ---------------------------------------------------------------------------


class TestSSEIntegration:
    @pytest.mark.asyncio
    async def test_ws_event_to_sse_pipeline(self):
        """Full pipeline: on_event → state update + publish → SSE output."""
        mgr = DeviceStateManager()

        # Simulate WS event arriving
        vol_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(actual=33, target=33, muted=False),
        )

        # Subscribe before event arrives
        queue = mgr.subscribe()

        # Process event (as WebSocketManager would)
        await mgr.on_event(vol_event)

        # State should be updated
        state = mgr.get_state("D1")
        assert state is not None
        assert state.volume.actual == 33

        # Subscriber should have received the event
        received = await queue.get()
        assert received is vol_event

        # SSE formatting should produce valid output
        sse = _event_to_sse(received)
        assert "event: volume" in sse
        data = json.loads(sse.split("data: ")[1].strip())
        assert data["device_id"] == "D1"
        assert data["actual"] == 33

    @pytest.mark.asyncio
    async def test_ws_event_through_stream_generator(self):
        """on_event → state update → generator yields snapshot with updated data."""
        mgr = DeviceStateManager()

        req = MagicMock()
        # Disconnect immediately after snapshot
        req.is_disconnected = AsyncMock(return_value=True)

        # Process event first (updates state)
        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="BLUETOOTH", state="PLAY_STATE", track="Test Song"
            ),
        )
        await mgr.on_event(event)

        # Generator should yield snapshot from state (now_playing cached)
        messages = []
        async for msg in _stream_events(req, mgr):
            messages.append(msg)

        joined = "".join(messages)
        assert "event: now_playing" in joined
        assert "Test Song" in joined
