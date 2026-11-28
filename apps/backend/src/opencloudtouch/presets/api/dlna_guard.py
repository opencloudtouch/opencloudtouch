"""Guard: DLNA presets live on the speaker and have no stream URL."""

from opencloudtouch.core.error_codes import DLNA_PRESET_NOT_STREAMABLE
from opencloudtouch.core.exceptions import raise_coded
from opencloudtouch.presets.models import Preset


def reject_dlna_preset(preset: Preset) -> None:
    if preset.is_dlna:
        raise_coded(409, DLNA_PRESET_NOT_STREAMABLE, "DLNA presets have no stream URL")
