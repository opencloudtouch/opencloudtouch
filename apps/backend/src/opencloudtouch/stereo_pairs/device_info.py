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
    "stereo_partner_name": None,
    "stereo_master_name": None,
    "stereo_pair_name": None,
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


def _is_capable(device: Any) -> bool:
    features = ((device.capabilities or {}).get("features")) or {}
    # Devices stored before the capability was detected have no "lr_stereo" value (None):
    # the model decides, and the create preflight checks the speaker live. Only an
    # explicit False excludes a device.
    return (
        SUPPORTED_MODEL in (device.model or "")
        and features.get("lr_stereo") is not False
    )


def _ineligible_reason(
    capable: bool, provisioned: bool, in_pair: bool, in_zone: bool
) -> Optional[str]:
    if not capable:
        return "not_capable"
    if not provisioned:
        return "not_provisioned"
    if in_pair:
        return "in_pair"
    if in_zone:
        return "in_zone"
    return None


def _pair_fields(
    device_id: str, pair: Optional[StereoPair], names: Dict[str, str]
) -> Dict[str, Any]:
    """Role, partner and master of the device inside its pair (empty outside a pair)."""
    if pair is None:
        return {
            "stereo_pair_id": None,
            "stereo_role": None,
            "stereo_master": False,
            "stereo_partner_name": None,
            "stereo_master_name": None,
            "stereo_pair_name": None,
        }
    is_left = pair.left_device_id == device_id
    partner_id = pair.right_device_id if is_left else pair.left_device_id
    return {
        "stereo_pair_id": pair.id,
        "stereo_role": "LEFT" if is_left else "RIGHT",
        "stereo_master": pair.master_device_id == device_id,
        "stereo_partner_name": names.get(partner_id),
        "stereo_master_name": names.get(pair.master_device_id),
        "stereo_pair_name": pair.name,
    }


def stereo_fields(
    device: Any,
    pairs: Dict[str, StereoPair],
    zone_device_ids: Set[str],
    names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Stereo fields for one device (stored data only, no live device calls).

    ``offline`` is not part of the reason: reachability is only known live and is
    checked by the create preflight.
    """
    capable = _is_capable(device)
    provisioned = bool(device.marge_account_uuid)
    pair = pairs.get(device.device_id)
    return {
        "stereo_capable": capable,
        "oct_provisioned": provisioned,
        "stereo_ineligible_reason": _ineligible_reason(
            capable,
            provisioned,
            pair is not None,
            device.device_id in zone_device_ids,
        ),
        **_pair_fields(device.device_id, pair, names or {}),
    }
