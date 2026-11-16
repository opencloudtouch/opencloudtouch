"""Guard for routes that need a stream URL, which a DLNA preset does not have."""

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import raise_coded
from opencloudtouch.presets.models import Preset


def reject_dlna_preset(preset: Preset) -> None:
    """409 for a DLNA preset: it is resolved by the speaker at press time."""
    if preset.source == "DLNA":
        raise_coded(
            409,
            error_codes.DLNA_PRESET_NOT_STREAMABLE,
            "DLNA presets have no stream URL",
        )
