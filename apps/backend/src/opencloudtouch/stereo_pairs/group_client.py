"""Speaker-side group API (port 8090): info, capabilities, group, zone.

A thin httpx client kept separate from ``DeviceClient`` so the existing device
client interface and its implementations stay untouched.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import httpx
from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.core.logging import clip_for_log

logger = logging.getLogger(__name__)

SOUNDTOUCH_HTTP_PORT = 8090
# The speaker retries its Marge call about every 15 s; leave room for a few tries.
ADD_GROUP_TIMEOUT = 45.0
READ_TIMEOUT = 5.0
NO_GROUP_TO_REMOVE = "GROUP_NO_GROUP_TO_REMOVE_ERROR"
GROUP_ALREADY_EXISTS = "GROUP_ALREADY_EXISTS_ERROR"


class GroupClientError(Exception):
    """A speaker call failed. ``uncertain`` is True when the outcome is unknown
    (timeout, connection lost): the speaker may or may not have applied it."""

    def __init__(
        self, message: str, *, code: str | None = None, uncertain: bool = False
    ):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


@dataclass
class SpeakerInfo:
    device_id: str
    name: str
    type: str
    marge_account_uuid: str
    firmware: str
    lr_stereo_capable: bool = False


@dataclass
class GroupState:
    id: Optional[str]
    name: str
    master_id: str
    roles: Dict[str, str] = field(default_factory=dict)  # device_id -> LEFT|RIGHT


class GroupClient(Protocol):
    async def get_info(self) -> SpeakerInfo: ...

    async def get_group(self) -> Optional[GroupState]: ...

    async def get_zone_member_ids(self) -> List[str]: ...

    async def add_group(
        self,
        name: str,
        master_id: str,
        roles: Dict[str, tuple[str, str]],
        *,
        group_id: Optional[str] = None,
        sender_ip: Optional[str] = None,
    ) -> Optional[str]: ...

    async def update_group(
        self,
        name: str,
        master_id: str,
        roles: Dict[str, tuple[str, str]],
        group_id: str,
    ) -> None: ...

    async def remove_group(self) -> None: ...


def parse_group(root: ET.Element) -> Optional[GroupState]:
    """Parse a <group> element; an empty element means "not in a group"."""
    master = (root.findtext("masterDeviceId") or "").strip()
    if not master:
        return None
    roles: Dict[str, str] = {}
    for role in root.findall("./roles/groupRole"):
        device_id = (role.findtext("deviceId") or "").strip()
        role_name = (role.findtext("role") or "").strip().upper()
        if device_id and role_name:
            roles[device_id] = role_name
    return GroupState(
        root.get("id"), (root.findtext("name") or "").strip(), master, roles
    )


class HttpGroupClient:
    """GroupClient for a real speaker."""

    def __init__(self, ip: str):
        self.ip = ip
        # SoundTouch speakers only speak plain HTTP on the LAN
        self._base = f"http://{ip}:{SOUNDTOUCH_HTTP_PORT}"  # NOSONAR

    async def _request(
        self,
        method: str,
        path: str,
        *,
        content: str | None = None,
        max_seconds: float = READ_TIMEOUT,
        content_type: str = "text/xml",
    ) -> ET.Element:
        logger.debug(
            "[SPEAKER] -> %s %s %s %s", method, self.ip, path, clip_for_log(content)
        )
        try:
            async with httpx.AsyncClient(timeout=max_seconds) as client:
                response = await client.request(
                    method,
                    f"{self._base}{path}",
                    content=content.encode("utf-8") if content is not None else None,
                    headers=(
                        {"Content-Type": content_type} if content is not None else None
                    ),
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.debug("[SPEAKER] !! %s %s %s", self.ip, path, type(exc).__name__)
            raise GroupClientError(
                f"{path} on {self.ip}: {type(exc).__name__}", uncertain=True
            ) from exc
        logger.debug(
            "[SPEAKER] <- %s %s %s %s",
            response.status_code,
            self.ip,
            path,
            clip_for_log(response.text),
        )
        try:
            root = parse_xml_string(response.content)
        except (ParseError, ValueError) as exc:
            raise GroupClientError(f"{path} on {self.ip}: invalid XML") from exc
        if root.tag == "errors":
            error = root.find("error")
            code = error.get("name") if error is not None else None
            raise GroupClientError(f"{path} on {self.ip}: {code or 'error'}", code=code)
        return root

    async def get_info(self) -> SpeakerInfo:
        info = await self._request("GET", "/info")
        firmware = ""
        for component in info.findall("./components/component"):
            if component.findtext("componentCategory") == "SCM":
                firmware = (component.findtext("softwareVersion") or "").split(" ")[0]
        capabilities = await self._request("GET", "/capabilities")
        lr = (capabilities.findtext("lrStereoCapable") or "").strip().lower() == "true"
        return SpeakerInfo(
            device_id=info.get("deviceID", ""),
            name=(info.findtext("name") or "").strip(),
            type=(info.findtext("type") or "").strip(),
            marge_account_uuid=(info.findtext("margeAccountUUID") or "").strip(),
            firmware=firmware,
            lr_stereo_capable=lr,
        )

    async def get_group(self) -> Optional[GroupState]:
        return parse_group(await self._request("GET", "/getGroup"))

    async def get_zone_member_ids(self) -> List[str]:
        zone = await self._request("GET", "/getZone")
        ids = [m.text.strip() for m in zone.findall("member") if m.text]
        master = zone.get("master")
        members = [master] if master else []
        return members + ids

    async def add_group(
        self,
        name: str,
        master_id: str,
        roles: Dict[str, tuple[str, str]],
        *,
        group_id: Optional[str] = None,
        sender_ip: Optional[str] = None,
    ) -> Optional[str]:
        """Ask the speaker to create/join a group. ``roles``: device_id -> (role, ip)."""
        group_attr = f' id="{escape(group_id)}"' if group_id else ""
        entries = "".join(
            f"<groupRole><deviceId>{escape(device_id)}</deviceId>"
            f"<role>{role}</role><ipAddress>{escape(ip)}</ipAddress></groupRole>"
            for device_id, (role, ip) in roles.items()
        )
        sender = (
            f"<senderIPAddress>{escape(sender_ip)}</senderIPAddress>"
            if sender_ip
            else ""
        )
        body = (
            f"<group{group_attr}><name>{escape(name)}</name>"
            f"<masterDeviceId>{escape(master_id)}</masterDeviceId>"
            f"<roles>{entries}</roles>{sender}</group>"
        )
        response = await self._request(
            "POST", "/addGroup", content=body, max_seconds=ADD_GROUP_TIMEOUT
        )
        return response.get("id")

    async def update_group(
        self,
        name: str,
        master_id: str,
        roles: Dict[str, tuple[str, str]],
        group_id: str,
    ) -> None:
        """Rename the group: a POST of the whole group.

        A PUT is answered with 405 and a name-only body with 5540 (checked on a real
        SoundTouch 10, firmware 27.0.6).
        """
        entries = "".join(
            f"<groupRole><deviceId>{escape(device_id)}</deviceId>"
            f"<role>{role}</role><ipAddress>{escape(ip)}</ipAddress></groupRole>"
            for device_id, (role, ip) in roles.items()
        )
        body = (
            f'<group id="{escape(group_id)}"><name>{escape(name)}</name>'
            f"<masterDeviceId>{escape(master_id)}</masterDeviceId>"
            f"<roles>{entries}</roles></group>"
        )
        await self._request(
            "POST",
            "/updateGroup",
            content=body,
            max_seconds=ADD_GROUP_TIMEOUT,
            content_type="application/xml; charset=utf-8",
        )

    async def remove_group(self) -> None:
        try:
            await self._request("GET", "/removeGroup", max_seconds=ADD_GROUP_TIMEOUT)
        except GroupClientError as exc:
            # seen on a real SoundTouch 10 (5550): nothing to remove is the wanted end state
            if exc.code != NO_GROUP_TO_REMOVE:
                raise


def get_group_client(ip: str) -> GroupClient:
    return HttpGroupClient(ip)
