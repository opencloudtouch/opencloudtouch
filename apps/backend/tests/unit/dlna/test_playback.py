"""Tests for DLNA playback queue management."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.models import DlnaItem
from opencloudtouch.dlna.playback import DlnaPlaybackError, DlnaPlaybackService


def make_renderer() -> AsyncMock:
    """Provide the default UPnP source for a playing test renderer."""
    renderer = AsyncMock()
    renderer.get_source.return_value = "UPNP"
    return renderer


def make_track(track_id: str, url: str) -> DlnaItem:
    """Create a playable DLNA test item."""
    return DlnaItem(
        id=track_id,
        parent_id="1$4",
        title=track_id,
        is_container=False,
        resource_url=url,
        media_class="object.item.audioItem.musicTrack",
    )


def make_tracks(count: int) -> list[DlnaItem]:
    """Build a queue with predictable track IDs and resource URLs."""
    return [
        make_track(f"track-{i}", f"http://server/{i}.mp3") for i in range(1, count + 1)
    ]


async def start_queue(
    service: DlnaPlaybackService, count: int = 2, initial_id: str = "track-1"
) -> list[DlnaItem]:
    """Start a DLNA queue for playback tests."""
    tracks = make_tracks(count)
    await service.play("device-1", "192.0.2.10", "server-1", tracks, initial_id)
    return tracks


@pytest.mark.asyncio
async def test_play_creates_queue():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    result = await service.play(
        device_id="device-1",
        device_ip="192.0.2.10",
        server_id="server-1",
        items=[first, second],
        object_id="track-1",
    )

    assert result == first
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/1.mp3",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("direction", "initial_id", "expected_id", "expected_url"),
    [
        ("next", "track-1", "track-2", "http://server/2.mp3"),
        ("previous", "track-2", "track-1", "http://server/1.mp3"),
    ],
)
async def test_manual_track_navigation(
    direction, initial_id, expected_id, expected_url
):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    tracks = [
        make_track("track-1", "http://server/1.mp3"),
        make_track("track-2", "http://server/2.mp3"),
    ]
    await service.play("device-1", "192.0.2.10", "server-1", tracks, initial_id)
    renderer.reset_mock()

    result = await getattr(service, direction)("device-1", "192.0.2.10")

    assert result.id == expected_id
    renderer.play_uri.assert_awaited_once_with("192.0.2.10", expected_url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("direction", "error"),
    [("next", "No next"), ("previous", "No previous")],
)
async def test_manual_navigation_at_queue_boundary(direction, error):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    track = make_track("track-1", "http://server/1.mp3")
    await service.play("device-1", "192.0.2.10", "server-1", [track], "track-1")

    with pytest.raises(DlnaPlaybackError, match=error):
        await getattr(service, direction)("device-1", "192.0.2.10")
    renderer.play_uri.assert_awaited_once()


@pytest.mark.asyncio
async def test_pause_and_resume():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    await service.pause("device-1", "192.0.2.10")
    await service.resume("device-1", "192.0.2.10")

    renderer.pause.assert_awaited_once_with("192.0.2.10")
    renderer.resume.assert_awaited_once_with("192.0.2.10")


@pytest.mark.asyncio
async def test_resume_after_oct_pause_event():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)

    await service.pause("device-1", "192.0.2.10")
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")
    assert service.current("device-1") is not None

    await service.resume("device-1", "192.0.2.10")

    renderer.resume.assert_awaited_once_with("192.0.2.10")
    assert service.current("device-1") is not None


@pytest.mark.asyncio
async def test_resume_refuses_radio_after_oct_pause():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)

    await service.pause("device-1", "192.0.2.10")
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")
    renderer.get_source.return_value = "LOCAL_INTERNET_RADIO"

    with pytest.raises(DlnaPlaybackError, match="No active DLNA playback"):
        await service.resume("device-1", "192.0.2.10")

    renderer.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_playback_state():
    service = DlnaPlaybackService(renderer=AsyncMock())

    with pytest.raises(DlnaPlaybackError, match="No active"):
        await service.next("missing-device", "192.0.2.10")


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["next", "previous", "pause", "resume"])
async def test_manual_controls_reject_inactive_queue_after_source_switch(action):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service, count=3, initial_id="track-2")
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    # A source switch ends the DLNA session without clearing its stored queue.
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")
    assert service.current("device-1") is None

    with pytest.raises(DlnaPlaybackError, match="No active DLNA playback"):
        await getattr(service, action)("device-1", "192.0.2.10")

    renderer.play_uri.assert_not_awaited()
    renderer.pause.assert_not_awaited()
    renderer.resume.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["next", "previous", "pause", "resume"])
async def test_manual_controls_reject_finished_queue(action):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service, count=1)
    await service.handle_transport_state("device-1", "PLAYING")
    await service.handle_transport_state("device-1", "STOPPED")
    renderer.reset_mock()

    with pytest.raises(DlnaPlaybackError, match="No active DLNA playback"):
        await getattr(service, action)("device-1", "192.0.2.10")

    renderer.play_uri.assert_not_awaited()
    renderer.pause.assert_not_awaited()
    renderer.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_stopped_without_playing_does_not_advance():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second],
        "track-1",
    )
    renderer.reset_mock()

    result = await service.handle_transport_state("device-1", "STOPPED")

    assert result is None
    renderer.play_uri.assert_not_awaited()


@pytest.mark.asyncio
async def test_playing_then_stopped_advances_queue():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second],
        "track-1",
    )
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "PLAYING")
    result = await service.handle_transport_state("device-1", "STOPPED")

    assert result is None
    await asyncio.sleep(0.5)
    assert service.current("device-1") == second
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/2.mp3",
    )


@pytest.mark.asyncio
async def test_extra_stopped_after_advance_does_not_advance_again():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")
    third = make_track("track-3", "http://server/3.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second, third],
        "track-1",
    )
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "PLAYING")
    first_result = await service.handle_transport_state("device-1", "STOPPED")
    second_result = await service.handle_transport_state("device-1", "STOPPED")

    assert first_result is None
    await asyncio.sleep(0.5)
    assert service.current("device-1") == second
    assert second_result is None
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/2.mp3",
    )


@pytest.mark.asyncio
async def test_stopped_at_queue_end_does_not_fail():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "PLAYING")
    result = await service.handle_transport_state("device-1", "STOPPED")

    assert result is None
    renderer.play_uri.assert_not_awaited()


@pytest.mark.asyncio
async def test_current_returns_active_item():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    assert service.current("device-1") == track


@pytest.mark.asyncio
async def test_current_is_empty_after_final_track_stops():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    await service.handle_transport_state("device-1", "PLAYING")
    await service.handle_transport_state("device-1", "STOPPED")

    assert service.current("device-1") is None


@pytest.mark.asyncio
async def test_failed_initial_play_does_not_create_active_queue():
    renderer = make_renderer()
    renderer.play_uri.side_effect = RuntimeError("UPnP failed")
    service = DlnaPlaybackService(renderer=renderer)
    first = make_track("track-1", "http://server/1.mp3")

    with pytest.raises(RuntimeError, match="UPnP failed"):
        await service.play(
            "device-1",
            "192.0.2.10",
            "server-1",
            [first],
            "track-1",
        )

    assert service.current("device-1") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("direction", "initial_id"),
    [("next", "track-1"), ("previous", "track-2")],
)
async def test_failed_manual_navigation_keeps_current_track(direction, initial_id):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    tracks = [
        make_track("track-1", "http://server/1.mp3"),
        make_track("track-2", "http://server/2.mp3"),
    ]
    await service.play("device-1", "192.0.2.10", "server-1", tracks, initial_id)
    renderer.play_uri.side_effect = RuntimeError("UPnP failed")

    with pytest.raises(RuntimeError, match="UPnP failed"):
        await getattr(service, direction)("device-1", "192.0.2.10")

    assert service.current("device-1").id == initial_id


@pytest.mark.asyncio
async def test_concurrent_stopped_events_advance_only_once():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    tracks = await start_queue(service, count=3)

    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_play(device_ip, url):
        entered.set()
        await release.wait()

    renderer.play_uri.side_effect = slow_play

    first = asyncio.create_task(service.handle_transport_state("device-1", "STOPPED"))

    await asyncio.wait_for(entered.wait(), timeout=2)

    second = asyncio.create_task(service.handle_transport_state("device-1", "STOPPED"))

    release.set()
    await asyncio.sleep(0.5)
    results = await asyncio.gather(first, second)

    assert results == [None, None]
    await asyncio.sleep(0)
    assert service.current("device-1") == tracks[1]
    renderer.play_uri.assert_awaited_once_with("192.0.2.10", "http://server/2.mp3")


@pytest.mark.asyncio
async def test_manual_next_during_automatic_advance():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    tracks = await start_queue(service, count=3)
    await service.handle_transport_state("device-1", "PLAYING")

    renderer.reset_mock()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_play(device_ip, url):
        entered.set()
        await release.wait()

    renderer.play_uri.side_effect = slow_play

    automatic = asyncio.create_task(
        service.handle_transport_state("device-1", "STOPPED")
    )
    await asyncio.wait_for(entered.wait(), timeout=2)

    manual = asyncio.create_task(service.next("device-1", "192.0.2.10"))

    # Give the manual operation a chance to start.
    await asyncio.sleep(0)
    release.set()

    await asyncio.gather(automatic, manual)

    assert service.current("device-1") == tracks[2]

    urls = [call.args[1] for call in renderer.play_uri.await_args_list]
    assert urls == [
        "http://server/2.mp3",
        "http://server/3.mp3",
    ]


@pytest.mark.asyncio
async def test_different_devices_can_play_concurrently():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    track = make_track("track-1", "http://server/1.mp3")

    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_finished = asyncio.Event()

    async def controlled_play(device_ip, url):
        if device_ip == "192.0.2.10":
            first_started.set()
            await release_first.wait()
        else:
            second_finished.set()

    renderer.play_uri.side_effect = controlled_play

    first = asyncio.create_task(
        service.play("device-1", "192.0.2.10", "server-1", [track], "track-1")
    )

    try:
        await asyncio.wait_for(first_started.wait(), timeout=2)

        second = await asyncio.wait_for(
            service.play("device-2", "192.0.2.11", "server-1", [track], "track-1"),
            timeout=2,
        )

        assert second == track
        assert second_finished.is_set()
        assert service.current("device-2") == track
    finally:
        release_first.set()
        await first


@pytest.mark.asyncio
async def test_device_lock_released_after_playback_failure():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play("device-1", "192.0.2.10", "server-1", [first, second], "track-1")

    renderer.play_uri.side_effect = RuntimeError("UPnP failed")

    with pytest.raises(RuntimeError, match="UPnP failed"):
        await service.next("device-1", "192.0.2.10")

    renderer.play_uri.side_effect = None

    result = await service.next("device-1", "192.0.2.10")

    assert result == second
    assert service.current("device-1") == second


@pytest.mark.asyncio
async def test_radio_source_switch_does_not_advance_dlna_queue():
    """A source switch must cancel pending automatic advancement."""
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    await start_queue(service, count=2)

    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    # Radio was selected by the time STOPPED arrived.
    renderer.get_source.return_value = "LOCAL_INTERNET_RADIO"
    await service.handle_transport_state("device-1", "STOPPED")
    await asyncio.sleep(0)
    if service._advance_tasks:
        await asyncio.gather(*service._advance_tasks.values())
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")

    renderer.play_uri.assert_not_awaited()
    assert service.current("device-1") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["next", "previous"])
async def test_manual_navigation_refuses_radio_after_oct_pause(direction):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service, count=3, initial_id="track-2")
    await service.pause("device-1", "192.0.2.10")
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")
    renderer.reset_mock()
    renderer.get_source.return_value = "LOCAL_INTERNET_RADIO"

    with pytest.raises(DlnaPlaybackError, match="No active DLNA playback"):
        await getattr(service, direction)("device-1", "192.0.2.10")

    assert service.current("device-1") is None
    renderer.play_uri.assert_not_awaited()


@pytest.mark.asyncio
async def test_late_playing_event_does_not_reactivate_abandoned_dlna_queue():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service, count=3)
    await service.handle_transport_state("device-1", "PLAYING")
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")
    assert service.current("device-1") is None

    await service.handle_transport_state("device-1", "PLAYING")

    assert service.current("device-1") is None
    renderer.play_uri.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_navigation_works_during_oct_pause():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    tracks = await start_queue(service, count=3)
    await service.pause("device-1", "192.0.2.10")
    await service.handle_transport_state("device-1", "PAUSED_PLAYBACK")

    result = await service.next("device-1", "192.0.2.10")

    assert result == tracks[1]
    assert service.current("device-1") == tracks[1]


@pytest.mark.asyncio
async def test_automatic_advance_checks_upnp_source():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    tracks = await start_queue(service)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "STOPPED")
    await service._advance_tasks["device-1"]

    renderer.get_source.assert_awaited_once_with("192.0.2.10")
    renderer.play_uri.assert_awaited_once_with("192.0.2.10", tracks[1].resource_url)
    assert service.current("device-1") == tracks[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["LOCAL_INTERNET_RADIO", "BLUETOOTH", "AUX", ""])
async def test_automatic_advance_ignores_other_sources(source):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()
    renderer.get_source.return_value = source

    await service.handle_transport_state("device-1", "STOPPED")
    await service._advance_tasks["device-1"]

    renderer.play_uri.assert_not_awaited()
    assert service.current("device-1") is None


@pytest.mark.asyncio
async def test_automatic_advance_source_error_does_not_restart(caplog):
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()
    renderer.get_source.side_effect = RuntimeError("source unavailable")

    await service.handle_transport_state("device-1", "STOPPED")
    await service._advance_tasks["device-1"]

    renderer.play_uri.assert_not_awaited()
    assert service.current("device-1") is None
    assert "DLNA automatic track advance failed" in caplog.text


@pytest.mark.asyncio
async def test_manual_next_cancels_pending_automatic_advance():
    """Manual next must cancel a pending source verification."""
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    tracks = await start_queue(service, count=3)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    entered = asyncio.Event()

    checks = 0

    async def slow_source(_device_ip):
        nonlocal checks
        checks += 1
        if checks == 1:
            entered.set()
            await asyncio.Event().wait()
        return "UPNP"

    renderer.get_source.side_effect = slow_source
    await service.handle_transport_state("device-1", "STOPPED")
    await asyncio.wait_for(entered.wait(), timeout=2)

    # Manual next cancels the source check before it starts a track.
    result = await service.next("device-1", "192.0.2.10")
    assert result == tracks[1]

    assert service.current("device-1") == tracks[1]
    renderer.play_uri.assert_awaited_once_with("192.0.2.10", "http://server/2.mp3")


@pytest.mark.asyncio
async def test_close_cancels_pending_automatic_advance():
    """Shutdown must prevent scheduled playback from starting."""
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    await start_queue(service, count=2)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    entered = asyncio.Event()

    async def slow_source(_device_ip):
        entered.set()
        await asyncio.Event().wait()

    renderer.get_source.side_effect = slow_source
    await service.handle_transport_state("device-1", "STOPPED")
    await asyncio.wait_for(entered.wait(), timeout=2)

    assert len(service._advance_tasks) == 1

    await service.close()
    renderer.play_uri.assert_not_awaited()
    assert service._advance_tasks == {}


@pytest.mark.asyncio
async def test_manual_next_during_inflight_delayed_advance():
    """Manual next during an active automatic call must remain ordered."""
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)

    tracks = await start_queue(service, count=3)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.reset_mock()

    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_play(device_ip, url):
        entered.set()
        await release.wait()

    renderer.play_uri.side_effect = slow_play

    await service.handle_transport_state("device-1", "STOPPED")

    # Wait until the delayed automatic advance reaches the renderer.
    await asyncio.wait_for(entered.wait(), timeout=2)

    manual = asyncio.create_task(service.next("device-1", "192.0.2.10"))

    await asyncio.sleep(0)
    release.set()

    result = await asyncio.wait_for(manual, timeout=2)
    assert result == tracks[2]
    assert service.current("device-1") == tracks[2]

    assert renderer.play_uri.await_count == 2


@pytest.mark.asyncio
async def test_automatic_advance_network_error_is_logged(caplog):
    """A failed automatic UPnP command must be logged without changing index."""
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)
    await service.handle_transport_state("device-1", "PLAYING")
    renderer.play_uri.side_effect = RuntimeError("renderer offline")
    await service.handle_transport_state("device-1", "STOPPED")
    task = service._advance_tasks["device-1"]
    await task
    assert service._states["device-1"].index == 0
    assert service.current("device-1") is None
    assert "DLNA automatic track advance failed" in caplog.text
    assert "renderer offline" in caplog.text
    assert service._advance_tasks == {}


@pytest.mark.asyncio
async def test_pause_event_does_not_cancel_inflight_network_command():
    """An external pause must not abort an already-started UPnP command."""
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)
    await service.handle_transport_state("device-1", "PLAYING")
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_play(device_ip, url):
        entered.set()
        await release.wait()

    renderer.play_uri.side_effect = slow_play
    await service.handle_transport_state("device-1", "STOPPED")
    await asyncio.wait_for(entered.wait(), timeout=2)
    pause = asyncio.create_task(
        service.handle_transport_state("device-1", "PAUSED_PLAYBACK")
    )
    await asyncio.sleep(0)
    release.set()
    await asyncio.wait_for(pause, timeout=2)
    assert service._states["device-1"].index == 1
    assert service.current("device-1") is None
    assert service._advance_tasks == {}


@pytest.mark.asyncio
async def test_events_after_shutdown_do_not_restart_queue():
    renderer = make_renderer()
    service = DlnaPlaybackService(renderer=renderer)
    await start_queue(service)
    await service.close()
    renderer.reset_mock()
    await service.handle_transport_state("device-1", "PLAYING")
    await service.handle_transport_state("device-1", "STOPPED")
    assert renderer.play_uri.await_count == 0
    assert service._advance_tasks == {}
