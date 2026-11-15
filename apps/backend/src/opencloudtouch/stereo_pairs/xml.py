"""XML (de)serialization for the Marge group endpoints used by SoundTouch speakers."""

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as parse_xml_string

from opencloudtouch.stereo_pairs.repository import StereoPair

# Error codes of the group answers. They are defined by OCT: the codes of the
# original Bose server are not known.
MARGE_ERROR_DEVICE_IN_GROUP = "4041"
MARGE_ERROR_UNKNOWN_DEVICE = "4012"
MARGE_ERROR_INVALID_REQUEST = "4000"

_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
EMPTY_GROUP_XML = (_XML_DECLARATION + "<group/>").encode()
GROUP_DELETED_XML = (
    _XML_DECLARATION + "<status>Group deleted successfully</status>"
).encode()
GROUP_TEARDOWN_XML = (
    _XML_DECLARATION + "<status>Group teardown acknowledged</status>"
).encode()


class InvalidGroupError(ValueError):
    """Raised when a group request body is malformed or violates group rules."""


@dataclass
class GroupRequest:
    master_device_id: str
    name: str
    left_device_id: str
    right_device_id: str


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def parse_group_request(body: bytes) -> GroupRequest:
    """Parse a Marge create/update group body (extra fields are ignored)."""
    try:
        root = parse_xml_string(body)
    except (ParseError, ValueError) as exc:
        raise InvalidGroupError("Request body is not valid XML") from exc
    if root.tag != "group":
        raise InvalidGroupError("Root element must be <group>")

    roles: dict[str, str] = {}
    for role in root.findall("./roles/groupRole"):
        role_name = _text(role, "role").upper()
        device_id = _text(role, "deviceId")
        if role_name in ("LEFT", "RIGHT") and device_id:
            roles.setdefault(role_name, device_id)

    master = _text(root, "masterDeviceId")
    name = _text(root, "name")
    # Updates may carry only a name; callers that need roles validate them.
    return GroupRequest(master, name, roles.get("LEFT", ""), roles.get("RIGHT", ""))


def validate_create_request(request: GroupRequest) -> None:
    if not request.left_device_id or not request.right_device_id:
        raise InvalidGroupError("Group must have a LEFT and a RIGHT device")
    if request.left_device_id == request.right_device_id:
        raise InvalidGroupError("LEFT and RIGHT must be different devices")
    if request.master_device_id not in (
        request.left_device_id,
        request.right_device_id,
    ):
        raise InvalidGroupError("Master device must be the LEFT or the RIGHT device")


def build_group_xml(pair: StereoPair) -> bytes:
    group = ET.Element("group", id=str(pair.id))
    # element order and declaration match what the speaker itself reports on /getGroup
    ET.SubElement(group, "name").text = pair.name
    ET.SubElement(group, "masterDeviceId").text = pair.master_device_id
    roles = ET.SubElement(group, "roles")
    for device_id, role in (
        (pair.left_device_id, "LEFT"),
        (pair.right_device_id, "RIGHT"),
    ):
        entry = ET.SubElement(roles, "groupRole")
        ET.SubElement(entry, "deviceId").text = device_id
        ET.SubElement(entry, "role").text = role
    return (_XML_DECLARATION + ET.tostring(group, encoding="unicode")).encode()


def build_error_xml(status_code: str, message: str) -> bytes:
    error = ET.Element("error")
    ET.SubElement(error, "status-code").text = status_code
    ET.SubElement(error, "message").text = message
    return ET.tostring(error, encoding="utf-8", xml_declaration=True)
