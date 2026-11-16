"""Reference to a DLNA object stored in a preset (shared by all preset consumers).

A DLNA preset stores *where to find* the audio (media server UDN + object id),
never a playback URL: the URL is resolved from the server at press time.
"""

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote

DLNA_LOCATION_MAX_LENGTH = 1024  # safe default, hardware item H1 may only raise it
DLNA_OBJECT_ID_MAX = 512
DLNA_NAME_MAX = 200
# Hardware item H1: until a speaker has played a native track preset, tracks use the
# v1 reference path. A maintainer flips this one constant after the verification.
NATIVE_TRACK_PRESETS_VERIFIED = False
_TRACK_SUFFIX = " TRACK"
_SCHEME = "dlna://"
ORION_PATH = "/core02/svc-bmx-adapter-orion/prod/orion/station"


# Account of a media server on the speaker: the UPnP UUID plus ``/0``.
_SERVER_ACCOUNT = re.compile(
    r"^([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/0$"
)


def server_id_from_account(account: str) -> str | None:
    """Lower-case server UUID of a ``<uuid>/0`` account; ``None`` for anything else."""
    match = _SERVER_ACCOUNT.match(account)
    return match.group(1).lower() if match else None


def native_location(object_id: str, item_type: str) -> str:
    """Speaker ``location`` of a native item: tracks carry the `` TRACK`` suffix (H1)."""
    if NATIVE_TRACK_PRESETS_VERIFIED and item_type == "track":
        return object_id + _TRACK_SUFFIX
    return object_id


def strip_native_location(location: str, item_type: str) -> str:
    """Inverse of ``native_location`` for what the speaker reports back."""
    if (
        NATIVE_TRACK_PRESETS_VERIFIED
        and item_type == "track"
        and location.endswith(_TRACK_SUFFIX)
    ):
        return location[: -len(_TRACK_SUFFIX)]
    return location


class DlnaReferenceTooLongError(ValueError):
    """The Orion location of a reference would exceed ``DLNA_LOCATION_MAX_LENGTH``."""


@dataclass(frozen=True)
class DlnaReference:
    """Media server UDN (without ``uuid:``) and ContentDirectory object id."""

    server_id: str
    object_id: str


def to_station_url(ref: DlnaReference) -> str:
    """``dlna://<server_id>/<percent-encoded object_id>`` (reference holder in the DB)."""
    return f"{_SCHEME}{quote(ref.server_id, safe='')}/{quote(ref.object_id, safe='')}"


def from_station_url(url: str) -> DlnaReference | None:
    """Parse a ``dlna://`` station URL; ``None`` for anything else."""
    if not url.startswith(_SCHEME):
        return None
    server_id, _, object_id = url[len(_SCHEME) :].partition("/")
    if not server_id or not object_id:
        return None
    return DlnaReference(unquote(server_id), unquote(object_id))


def station_uuid(ref: DlnaReference) -> str:
    """Stable ``dlna-<16 hex>`` id (SHA-256, not the per-process randomised ``hash``)."""
    digest = hashlib.sha256(f"{ref.server_id}\0{ref.object_id}".encode()).hexdigest()
    return f"dlna-{digest[:16]}"


def build_orion_data(ref: DlnaReference, name: str) -> str:
    """Urlsafe base64 of ``{"dlna": {...}, "name": ...}`` (no URLs, name capped)."""
    payload = {
        "dlna": {"server_id": ref.server_id, "object_id": ref.object_id},
        "name": name[:DLNA_NAME_MAX],
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def parse_orion_data(data: str) -> tuple[DlnaReference, str] | None:
    """Decode Orion ``data``; ``None`` unless it carries a valid ``dlna`` reference."""
    try:
        padded = data + "=" * (-len(data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(payload, dict):
        return None
    dlna = payload.get("dlna")
    if not isinstance(dlna, dict):
        return None
    server_id, object_id = dlna.get("server_id"), dlna.get("object_id")
    if not (isinstance(server_id, str) and isinstance(object_id, str)):
        return None
    if not server_id or not object_id:
        return None
    name = payload.get("name")
    return DlnaReference(server_id, object_id), name if isinstance(name, str) else ""


def build_orion_location(
    oct_base_url: str, ref: DlnaReference, name: str, *, enforce_limit: bool = False
) -> str:
    """Orion adapter location for a reference.

    ``enforce_limit`` is for programming a speaker; rendering rows that are already
    stored (marge) must never fail.
    """
    location = f"{oct_base_url}{ORION_PATH}?data={build_orion_data(ref, name)}"
    if enforce_limit and len(location) > DLNA_LOCATION_MAX_LENGTH:
        raise DlnaReferenceTooLongError("DLNA preset reference is too long")
    return location
