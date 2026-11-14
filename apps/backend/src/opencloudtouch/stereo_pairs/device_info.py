"""Stereo pair fields of the device list (eligibility, role, partner)."""

from typing import Any, Dict, Optional, Set

from opencloudtouch.stereo_pairs.repository import StereoPair, StereoPairRepository
from opencloudtouch.zones.repository import ZoneRepository

SUPPORTED_MODEL = "SoundTouch 10"

NO_STEREO_INFO: Dict[str, Any] = {
    "stereo_capable": False,
    "oct_provisioned": False,
    "stereo_ineligible_reason": None,
    "stereo_pair_id": None,
    "stereo_role": None,
    "stereo_master": False,
}


async def load_stereo_context(
    stereo_repo: Optional[StereoPairRepository], zone_repo: Optional[ZoneRepository]
) -> tuple[Dict[str, StereoPair], Set[str]]:
    """Active pairs by device id and ids of all devices in active zones."""
    pairs: Dict[str, StereoPair] = {}
    if stereo_repo is not None:
        for pair in await stereo_repo.list_active():
            pairs[pair.left_device_id] = pair
            pairs[pair.right_device_id] = pair
    zone_ids: Set[str] = set()
    if zone_repo is not None:
        for zone in await zone_repo.get_all_active_zones():
            if zone.id is None:
                continue
            zone_ids.update(
                m.device_id for m in await zone_repo.get_active_members(zone.id)
            )
    return pairs, zone_ids


def stereo_fields(
    device: Any, pairs: Dict[str, StereoPair], zone_device_ids: Set[str]
) -> Dict[str, Any]:
    """Stereo fields for one device (stored data only, no live device calls).

    ``offline`` is not part of the reason: reachability is only known live and is
    checked by the create preflight.
    """
    features = ((device.capabilities or {}).get("features")) or {}
    # Devices stored before the capability was detected have no "lr_stereo" value (None):
    # the model decides, and the create preflight checks the speaker live. Only an
    # explicit False excludes a device.
    capable = (
        SUPPORTED_MODEL in (device.model or "")
        and features.get("lr_stereo") is not False
    )
    provisioned = bool(device.marge_account_uuid)
    pair = pairs.get(device.device_id)

    reason: Optional[str] = None
    if not capable:
        reason = "not_capable"
    elif not provisioned:
        reason = "not_provisioned"
    elif pair is not None:
        reason = "in_pair"
    elif device.device_id in zone_device_ids:
        reason = "in_zone"

    role = None
    if pair is not None:
        role = "LEFT" if pair.left_device_id == device.device_id else "RIGHT"
    return {
        "stereo_capable": capable,
        "oct_provisioned": provisioned,
        "stereo_ineligible_reason": reason,
        "stereo_pair_id": pair.id if pair else None,
        "stereo_role": role,
        "stereo_master": pair is not None and pair.master_device_id == device.device_id,
    }
