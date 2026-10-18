"""Tests for DLNA AVTransport event parsing."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.events import (
    DlnaEventSubscriptions,
    parse_avtransport_event,
)


def test_parse_avtransport_playing_event():
    body = """<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
  <e:property>
    <LastChange>&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;&lt;InstanceID val="0"&gt;&lt;TransportState val="PLAYING"/&gt;&lt;CurrentTrackURI val="http://media/track.mp3"/&gt;&lt;/InstanceID&gt;&lt;/Event&gt;</LastChange>
  </e:property>
</e:propertyset>"""

    event = parse_avtransport_event(body)

    assert event.transport_state == "PLAYING"
    assert event.current_track_uri == "http://media/track.mp3"


def test_parse_avtransport_stopped_event():
    body = """<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
  <e:property>
    <LastChange>&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;&lt;InstanceID val="0"&gt;&lt;TransportState val="STOPPED"/&gt;&lt;AVTransportURI val="qplay://"/&gt;&lt;/InstanceID&gt;&lt;/Event&gt;</LastChange>
  </e:property>
</e:propertyset>"""

    event = parse_avtransport_event(body)

    assert event.transport_state == "STOPPED"
    assert event.current_track_uri is None


@pytest.mark.asyncio
async def test_subscription_is_created():
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:test-subscription", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    await subscriptions.ensure(
        device_id="device-1",
        device_ip="192.0.2.10",
        callback_url="http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    renderer.subscribe.assert_awaited_once_with(
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    subscription = subscriptions._subscriptions["device-1"]
    assert subscription.sid == "uuid:test-subscription"
    assert subscription.timeout_seconds == 300

    await subscriptions.remove("device-1")


@pytest.mark.asyncio
async def test_existing_subscription_is_reused():
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:test-subscription", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )
    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    renderer.subscribe.assert_awaited_once()

    await subscriptions.remove("device-1")


@pytest.mark.asyncio
async def test_remove_unsubscribes():
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:test-subscription", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )
    await subscriptions.remove("device-1")

    renderer.unsubscribe.assert_awaited_once_with(
        "192.0.2.10",
        "uuid:test-subscription",
    )
    assert "device-1" not in subscriptions._subscriptions


@pytest.mark.asyncio
async def test_subscription_is_renewed(monkeypatch):
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:original", 300)
    renderer.renew_subscription.return_value = ("uuid:renewed", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    sleep_calls = 0

    async def fake_sleep(delay):
        nonlocal sleep_calls
        sleep_calls += 1

        assert delay == 240

        if sleep_calls > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    task = subscriptions._subscriptions["device-1"].renewal_task

    with pytest.raises(asyncio.CancelledError):
        await task

    renderer.renew_subscription.assert_awaited_once_with(
        "192.0.2.10",
        "uuid:original",
        300,
    )

    assert subscriptions._subscriptions["device-1"].sid == "uuid:renewed"


@pytest.mark.asyncio
async def test_concurrent_ensure_creates_only_one_subscription():
    renderer = AsyncMock()
    gate = asyncio.Event()
    entered = asyncio.Event()

    async def subscribe(device_ip, callback_url):
        entered.set()
        await gate.wait()
        return ("uuid:only-one", 300)

    renderer.subscribe.side_effect = subscribe
    subscriptions = DlnaEventSubscriptions(renderer)
    args = ("device-1", "192.0.2.10", "http://192.0.2.20:7777/callback")
    first = asyncio.create_task(subscriptions.ensure(*args))
    await asyncio.wait_for(entered.wait(), 2)
    second = asyncio.create_task(subscriptions.ensure(*args))
    gate.set()
    await asyncio.gather(first, second)

    renderer.subscribe.assert_awaited_once()
    await subscriptions.close()


@pytest.mark.asyncio
async def test_failed_renewal_recovers_with_fresh_subscription(monkeypatch):
    renderer = AsyncMock()
    renderer.subscribe.side_effect = [
        ("uuid:old", 300),
        ("uuid:recovered", 300),
    ]
    renderer.renew_subscription.side_effect = [
        RuntimeError("renewal failed"),
        asyncio.CancelledError(),
    ]
    subscriptions = DlnaEventSubscriptions(renderer)

    original_sleep = asyncio.sleep
    calls = 0

    async def controlled_sleep(_delay):
        nonlocal calls
        calls += 1
        if calls > 2:
            raise asyncio.CancelledError()
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", controlled_sleep)
    await subscriptions.ensure(
        "device-1", "192.0.2.10", "http://192.0.2.20:7777/callback"
    )
    subscription = subscriptions._subscriptions["device-1"]

    with pytest.raises(asyncio.CancelledError):
        await subscription.renewal_task

    assert subscription.sid == "uuid:recovered"
    assert renderer.subscribe.await_count == 2
    assert subscriptions._subscriptions["device-1"] is subscription


@pytest.mark.asyncio
async def test_exhausted_recovery_removes_only_own_subscription(monkeypatch):
    renderer = AsyncMock()
    renderer.subscribe.side_effect = [
        ("uuid:old", 300),
        RuntimeError("retry 1"),
        RuntimeError("retry 2"),
        RuntimeError("retry 3"),
    ]
    renderer.renew_subscription.side_effect = RuntimeError("renewal failed")
    subscriptions = DlnaEventSubscriptions(renderer)

    async def fast_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    await subscriptions.ensure(
        "device-1", "192.0.2.10", "http://192.0.2.20:7777/callback"
    )
    task = subscriptions._subscriptions["device-1"].renewal_task
    await asyncio.wait_for(task, 2)

    assert renderer.subscribe.await_count == 4
    assert "device-1" not in subscriptions._subscriptions
