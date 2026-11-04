"""UPnP AVTransport client for SoundTouch playback."""

import httpx
from defusedxml import ElementTree


class DlnaRendererError(Exception):
    """Raised when communication with a UPnP renderer fails."""


class DlnaRenderer:
    """Control SoundTouch playback through its UPnP AVTransport service."""

    AVTRANSPORT_SERVICE = "urn:schemas-upnp-org:service:AVTransport:1"

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    async def get_source(self, device_ip: str) -> str:
        """Read the active SoundTouch source through the Bose HTTP API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"http://{device_ip}:8090/now_playing")
                response.raise_for_status()
            return ElementTree.fromstring(response.content).attrib.get("source", "")
        except (httpx.HTTPError, ElementTree.ParseError) as exc:
            raise DlnaRendererError("SoundTouch source query failed") from exc

    async def play_uri(self, device_ip: str, uri: str) -> None:
        """Set a media URI on a SoundTouch device.

        The SoundTouch device retrieves the media resource directly from the
        media server; OCT does not proxy the audio stream. SoundTouch devices
        start playback automatically after SetAVTransportURI, so no separate
        Play action is required.
        """
        await self._send_action(
            device_ip,
            "SetAVTransportURI",
            f"""
      <InstanceID>0</InstanceID>
      <CurrentURI>{self._escape_xml(uri)}</CurrentURI>
      <CurrentURIMetaData></CurrentURIMetaData>
""",
        )

    async def subscribe(
        self,
        device_ip: str,
        callback_url: str,
        timeout_seconds: int = 300,
    ) -> tuple[str, int]:
        """Subscribe to SoundTouch AVTransport events exposed on port 8091."""
        url = f"http://{device_ip}:8091/AVTransport/Event"
        headers = {
            "CALLBACK": f"<{callback_url}>",
            "NT": "upnp:event",
            "TIMEOUT": f"Second-{timeout_seconds}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    "SUBSCRIBE",
                    url,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DlnaRendererError(
                "SoundTouch AVTransport subscription failed"
            ) from exc

        sid = response.headers.get("SID")
        if not sid:
            raise DlnaRendererError(
                "SoundTouch AVTransport subscription returned no SID"
            )

        granted_timeout = self._parse_subscription_timeout(
            response.headers.get("TIMEOUT"),
            timeout_seconds,
        )
        return sid, granted_timeout

    async def renew_subscription(
        self,
        device_ip: str,
        sid: str,
        timeout_seconds: int = 300,
    ) -> tuple[str, int]:
        """Renew an existing AVTransport event subscription."""
        url = f"http://{device_ip}:8091/AVTransport/Event"
        headers = {
            "SID": sid,
            "TIMEOUT": f"Second-{timeout_seconds}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    "SUBSCRIBE",
                    url,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DlnaRendererError(
                "SoundTouch AVTransport subscription renewal failed"
            ) from exc

        renewed_sid = response.headers.get("SID", sid)
        granted_timeout = self._parse_subscription_timeout(
            response.headers.get("TIMEOUT"),
            timeout_seconds,
        )
        return renewed_sid, granted_timeout

    async def unsubscribe(self, device_ip: str, sid: str) -> None:
        """Cancel an AVTransport event subscription."""
        url = f"http://{device_ip}:8091/AVTransport/Event"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    "UNSUBSCRIBE",
                    url,
                    headers={"SID": sid},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DlnaRendererError(
                "SoundTouch AVTransport unsubscribe failed"
            ) from exc

    @staticmethod
    def _parse_subscription_timeout(
        value: str | None,
        default: int,
    ) -> int:
        """Parse a UPnP TIMEOUT response header."""
        if not value or not value.lower().startswith("second-"):
            return default

        try:
            return int(value.split("-", 1)[1])
        except ValueError:
            return default

    async def pause(self, device_ip: str) -> None:
        """Pause current playback."""
        await self._send_action(
            device_ip,
            "Pause",
            """
      <InstanceID>0</InstanceID>
""",
        )

    async def resume(self, device_ip: str) -> None:
        """Resume current playback."""
        await self._send_action(
            device_ip,
            "Play",
            """
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
""",
        )

    async def _send_action(
        self,
        device_ip: str,
        action: str,
        body: str,
    ) -> None:
        """Send an AVTransport SOAP action to SoundTouch port 8091."""
        url = f"http://{device_ip}:8091/AVTransport/Control"

        payload = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="{self.AVTRANSPORT_SERVICE}">
{body.rstrip()}
    </u:{action}>
  </s:Body>
</s:Envelope>"""

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{self.AVTRANSPORT_SERVICE}#{action}"',
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    content=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DlnaRendererError(
                f"SoundTouch renderer request failed: {action}"
            ) from exc

    @staticmethod
    def _escape_xml(value: str) -> str:
        """Escape text inserted into SOAP XML."""
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
