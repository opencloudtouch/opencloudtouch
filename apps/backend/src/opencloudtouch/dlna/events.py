"""UPnP AVTransport event handling for DLNA playback."""

import asyncio
import logging
from dataclasses import dataclass
from defusedxml import ElementTree

from opencloudtouch.dlna.renderer import DlnaRenderer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvTransportEvent:
    """Relevant state from an AVTransport LastChange notification."""

    transport_state: str | None = None
    current_track_uri: str | None = None


def parse_avtransport_event(body: str) -> AvTransportEvent:
    """Parse a UPnP AVTransport NOTIFY body."""
    root = ElementTree.fromstring(body)

    last_change: str | None = None
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "LastChange":
            last_change = element.text
            break

    if not last_change:
        return AvTransportEvent()

    event_root = ElementTree.fromstring(last_change)

    transport_state: str | None = None
    current_track_uri: str | None = None

    for element in event_root.iter():
        name = element.tag.rsplit("}", 1)[-1]

        if name == "TransportState":
            transport_state = element.attrib.get("val")
        elif name == "CurrentTrackURI":
            current_track_uri = element.attrib.get("val")

    return AvTransportEvent(
        transport_state=transport_state,
        current_track_uri=current_track_uri,
    )


@dataclass
class DlnaSubscription:
    """Active SoundTouch AVTransport subscription."""

    device_id: str
    device_ip: str
    callback_url: str
    sid: str
    timeout_seconds: int
    renewal_task: asyncio.Task[None] | None = None


class DlnaEventSubscriptions:
    """Manage AVTransport subscriptions and their renewal."""

    def __init__(self, renderer: DlnaRenderer):
        self.renderer = renderer
        self._subscriptions: dict[str, DlnaSubscription] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._closed = False

    async def ensure(
        self,
        device_id: str,
        device_ip: str,
        callback_url: str,
    ) -> None:
        """Ensure one active subscription per device, even with concurrent callers."""
        async with self._locks.setdefault(device_id, asyncio.Lock()):
            if self._closed:
                return
            existing = self._subscriptions.get(device_id)
            if (
                existing is not None
                and existing.device_ip == device_ip
                and existing.callback_url == callback_url
                and existing.renewal_task is not None
                and not existing.renewal_task.done()
            ):
                return

            if existing is not None:
                await self._remove_locked(device_id)

            sid, timeout_seconds = await self.renderer.subscribe(
                device_ip, callback_url
            )
            subscription = DlnaSubscription(
                device_id=device_id,
                device_ip=device_ip,
                callback_url=callback_url,
                sid=sid,
                timeout_seconds=timeout_seconds,
            )
            self._subscriptions[device_id] = subscription
            subscription.renewal_task = asyncio.create_task(
                self._renew_loop(subscription)
            )
            logger.info(
                "DLNA AVTransport subscribed: device=%s timeout=%ss",
                device_id,
                timeout_seconds,
            )

    async def remove(self, device_id: str) -> None:
        """Remove and unsubscribe a device without racing with ensure."""
        async with self._locks.setdefault(device_id, asyncio.Lock()):
            await self._remove_locked(device_id)

    async def _remove_locked(self, device_id: str) -> None:
        subscription = self._subscriptions.pop(device_id, None)
        if subscription is None:
            return
        task = subscription.renewal_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        try:
            await self.renderer.unsubscribe(subscription.device_ip, subscription.sid)
        except Exception:
            logger.debug(
                "DLNA AVTransport unsubscribe failed: device=%s",
                device_id,
                exc_info=True,
            )

    async def close(self) -> None:
        """Stop renewals and prevent new subscriptions during shutdown."""
        self._closed = True
        for device_id in list(self._subscriptions):
            await self.remove(device_id)

    async def _renew_loop(self, subscription: DlnaSubscription) -> None:
        """Renew periodically, re-subscribing after transient renewal failures."""
        try:
            while True:
                delay = max(1, int(subscription.timeout_seconds * 0.8))
                await asyncio.sleep(delay)
                try:
                    sid, timeout_seconds = await self.renderer.renew_subscription(
                        subscription.device_ip,
                        subscription.sid,
                        subscription.timeout_seconds,
                    )
                except Exception:
                    logger.warning(
                        "DLNA AVTransport renewal failed; trying a fresh subscription: device=%s",
                        subscription.device_id,
                        exc_info=True,
                    )
                    # No busy loop: retry at most three times with backoff.
                    for attempt in range(3):
                        await asyncio.sleep(2**attempt)
                        try:
                            sid, timeout_seconds = await self.renderer.subscribe(
                                subscription.device_ip, subscription.callback_url
                            )
                            # A failed renewal does not prove the old SID is
                            # gone; release it to avoid duplicate notifications.
                            try:
                                await self.renderer.unsubscribe(
                                    subscription.device_ip, subscription.sid
                                )
                            except Exception:
                                logger.debug(
                                    "DLNA old subscription cleanup failed: device=%s",
                                    subscription.device_id,
                                    exc_info=True,
                                )
                            break
                        except Exception:
                            logger.warning(
                                "DLNA AVTransport re-subscription attempt %s failed: device=%s",
                                attempt + 1,
                                subscription.device_id,
                                exc_info=True,
                            )
                    else:
                        logger.warning(
                            "DLNA AVTransport recovery exhausted: device=%s",
                            subscription.device_id,
                        )
                        if (
                            self._subscriptions.get(subscription.device_id)
                            is subscription
                        ):
                            self._subscriptions.pop(subscription.device_id, None)
                        return

                subscription.sid = sid
                subscription.timeout_seconds = timeout_seconds
                logger.debug(
                    "DLNA AVTransport subscription renewed: device=%s timeout=%ss",
                    subscription.device_id,
                    timeout_seconds,
                )
        except asyncio.CancelledError:
            raise
