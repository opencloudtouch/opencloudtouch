"""Device settings: display language, standby clock and power saving.

Pure helpers shared by the HTTP client adapter, the mock client and the service:
language allow-list, XML parsing (``defusedxml``, never raising) and XML building.
The endpoint and element names come from a community patch and are hardware-unverified.
"""

import re
import zoneinfo
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from xml.etree.ElementTree import Element  # nosec B405 - type annotation only
from xml.sax.saxutils import quoteattr  # nosec B406 - escaping only, never parses

from defusedxml import ElementTree

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import raise_coded
from opencloudtouch.devices.client import (
    ClockSetting,
    LanguageSetting,
    PowerSavingSetting,
)

# Display languages the speaker firmware knows (id -> native name). 14 is unassigned.
LANGUAGES: dict[int, str] = {
    1: "Dansk",
    2: "Deutsch",
    3: "English",
    4: "Español",
    5: "Français",
    6: "Italiano",
    7: "Nederlands",
    8: "Svenska",
    9: "日本語",
    10: "简体中文",
    11: "繁體中文",
    12: "한국어",
    13: "ไทย",
    15: "Čeština",
    16: "Suomi",
    17: "Ελληνικά",
    18: "Norsk",
    19: "Polski",
    20: "Português",
    21: "Română",
    22: "Русский",
    23: "Slovenščina",
    24: "Türkçe",
    25: "Magyar",
}

TIME_FORMAT_24H = "24h"
TIME_FORMAT_12H = "12h"
TIME_FORMATS: tuple[str, ...] = (TIME_FORMAT_24H, TIME_FORMAT_12H)

_TIME_FORMAT_TO_WIRE = {
    TIME_FORMAT_24H: "TIME_FORMAT_24HOUR_ID",
    TIME_FORMAT_12H: "TIME_FORMAT_12HOUR_ID",
}
_WIRE_TO_TIME_FORMAT = {wire: api for api, wire in _TIME_FORMAT_TO_WIRE.items()}

_MAX_TIMEZONE_LENGTH = 64
_ATTRIBUTE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


@lru_cache(maxsize=1)
def _available_timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def is_valid_timezone(name: Any) -> bool:
    """True for an IANA name known to ``zoneinfo`` (``UTC`` or ``Area/Location``)."""
    if not isinstance(name, str) or not 0 < len(name) <= _MAX_TIMEZONE_LENGTH:
        return False
    if name != "UTC" and "/" not in name:
        return False  # rejects Factory, posixrules, localtime, POSIX TZ strings
    return name in _available_timezones()


def _parse_bool(text: str | None) -> bool | None:
    if text is None:
        return None
    value = text.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _find_element(xml: str, tag: str) -> Element | None:
    """Return *tag* as the root or as a descendant; None for anything unparsable."""
    try:
        root = ElementTree.fromstring(xml)
    except Exception:  # noqa: BLE001 - malformed input and XML bombs alike
        return None
    return root if root.tag == tag else root.find(f".//{tag}")


def parse_language(xml: str) -> LanguageSetting | None:
    """Parse ``<sysLanguage>N</sysLanguage>``."""
    element = _find_element(xml, "sysLanguage")
    if element is None or element.text is None:
        return None
    try:
        language_id = int(element.text.strip())
    except ValueError:
        return None
    return LanguageSetting(id=language_id, name=LANGUAGES.get(language_id))


def parse_clock(xml: str) -> ClockSetting | None:
    """Parse ``<clockConfig …/>`` (as root or inside ``<clockDisplay>``)."""
    element = _find_element(xml, "clockConfig")
    if element is None:
        return None
    attributes = dict(element.attrib)

    enabled_text = attributes.pop("userEnable", None)
    enabled = False if enabled_text is None else _parse_bool(enabled_text)

    time_format = _WIRE_TO_TIME_FORMAT.get(attributes.get("timeFormat", ""))
    if time_format is not None:
        attributes.pop("timeFormat")
    timezone = attributes.pop("timezoneInfo", None)
    return ClockSetting(
        enabled=enabled, time_format=time_format, timezone=timezone, extra=attributes
    )


def parse_power_saving(xml: str) -> PowerSavingSetting | None:
    """Parse ``<systemtimeout><powersaving_enabled>…``."""
    element = _find_element(xml, "systemtimeout")
    if element is None:
        return None
    flag = element.find("powersaving_enabled")
    if flag is None:
        return None
    return PowerSavingSetting(enabled=_parse_bool(flag.text))


def build_language_xml(language_id: int) -> str:
    return f"<sysLanguage>{int(language_id)}</sysLanguage>"


def build_power_saving_xml(enabled: bool) -> str:
    flag = "true" if enabled else "false"
    return (
        "<systemtimeout>"
        f"<powersaving_enabled>{flag}</powersaving_enabled>"
        "</systemtimeout>"
    )


def build_clock_xml(
    enabled: bool,
    time_format: str | None,
    timezone: str | None,
    extra: dict[str, str],
) -> str:
    """Build ``<clockDisplay><clockConfig …/></clockDisplay>``.

    Every attribute in *extra* (read from the device) is sent back unchanged; values
    and names are escaped/validated.
    """
    attributes: dict[str, str] = {
        name: value for name, value in extra.items() if _ATTRIBUTE_NAME.match(name)
    }
    attributes["userEnable"] = "true" if enabled else "false"
    if time_format is not None:
        attributes["timeFormat"] = _TIME_FORMAT_TO_WIRE[time_format]
    if timezone is not None:
        attributes["timezoneInfo"] = timezone
    rendered = " ".join(
        f"{name}={quoteattr(value)}" for name, value in attributes.items()
    )
    return f"<clockDisplay><clockConfig {rendered}/></clockDisplay>"


@dataclass
class DeviceSettings:
    """The three settings read from one device; None = not available."""

    language: LanguageSetting | None
    clock: ClockSetting | None
    power_saving: PowerSavingSetting | None

    @property
    def available(self) -> dict[str, bool]:
        return {
            "language": self.language is not None,
            "clock": self.clock is not None,
            "power_saving": self.power_saving is not None,
        }


@dataclass
class SettingWriteResult:
    """Outcome of a verified write: what the speaker reports after the POST."""

    applied: bool
    value: LanguageSetting | ClockSetting | PowerSavingSetting | None


def validate_language_id(value: Any) -> int:
    """Return *value* if it is an allow-listed language id, else raise 422."""
    if isinstance(value, bool) or not isinstance(value, int) or value not in LANGUAGES:
        raise_coded(
            422,
            error_codes.SETTINGS_LANGUAGE_INVALID,
            "Unsupported display language",
            field="language_id",
        )
    return value


def validate_enabled(value: Any) -> bool:
    """Return *value* if it is a real boolean, else raise 422."""
    if not isinstance(value, bool):
        raise_coded(
            422,
            error_codes.SETTINGS_ENABLED_INVALID,
            "'enabled' must be true or false",
            field="enabled",
        )
    return value


def validate_time_format(value: Any) -> str:
    if not isinstance(value, str) or value not in TIME_FORMATS:
        raise_coded(
            422,
            error_codes.SETTINGS_TIME_FORMAT_INVALID,
            "'time_format' must be '24h' or '12h'",
            field="time_format",
        )
    return value


def validate_timezone(value: Any) -> str:
    if not is_valid_timezone(value):
        raise_coded(
            422,
            error_codes.SETTINGS_TIMEZONE_INVALID,
            "'timezone' must be a valid IANA time zone name",
            field="timezone",
        )
    return value
