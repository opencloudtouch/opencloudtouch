"""Tests for KeyType enum and key mapping."""

from bosesoundtouchapi import SoundTouchKeys

from opencloudtouch.devices.models import KEY_MAPPING, KeyType


def test_key_type_values():
    """KeyType values match expected string identifiers."""
    assert KeyType.PLAY.value == "PLAY"
    assert KeyType.PAUSE.value == "PAUSE"
    assert KeyType.STOP.value == "STOP"
    assert KeyType.NEXT_TRACK.value == "NEXT_TRACK"
    assert KeyType.PREV_TRACK.value == "PREV_TRACK"
    assert KeyType.POWER.value == "POWER"
    assert KeyType.MUTE.value == "MUTE"


def test_key_mapping_covers_all_keys():
    """Every KeyType has a mapping to bosesoundtouchapi constants."""
    for key_type in KeyType:
        assert key_type in KEY_MAPPING


def test_key_mapping_targets_constants():
    """Mappings point to the correct SoundTouch key constants."""
    assert KEY_MAPPING[KeyType.PLAY] is SoundTouchKeys.PLAY
    assert KEY_MAPPING[KeyType.PAUSE] is SoundTouchKeys.PAUSE
    assert KEY_MAPPING[KeyType.STOP] is SoundTouchKeys.STOP
    assert KEY_MAPPING[KeyType.NEXT_TRACK] is SoundTouchKeys.NEXT_TRACK
    assert KEY_MAPPING[KeyType.PREV_TRACK] is SoundTouchKeys.PREV_TRACK
    assert KEY_MAPPING[KeyType.POWER] is SoundTouchKeys.POWER
    assert KEY_MAPPING[KeyType.MUTE] is SoundTouchKeys.MUTE
