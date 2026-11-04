"""Pure helpers for device settings (language, clock, power saving)."""

import pytest

from opencloudtouch.devices.client import (
    ClockSetting,
    LanguageSetting,
    PowerSavingSetting,
)
from opencloudtouch.devices.device_settings import (
    LANGUAGES,
    build_clock_xml,
    build_language_xml,
    build_power_saving_xml,
    is_valid_timezone,
    parse_clock,
    parse_language,
    parse_power_saving,
)

CLOCK_XML = (
    '<clockDisplay><clockConfig userEnable="true" timeFormat="TIME_FORMAT_24HOUR_ID" '
    'timezoneInfo="Europe/Berlin" userOffsetMinute="0" userUtcTime="0"/></clockDisplay>'
)


class TestLanguages:
    def test_allow_list_matches_the_spec_table(self):
        assert LANGUAGES[2] == "Deutsch"
        assert LANGUAGES[12] == "한국어"
        assert 14 not in LANGUAGES
        assert len(LANGUAGES) == 24
        assert sorted(LANGUAGES) == [*range(1, 14), *range(15, 26)]


class TestParseLanguage:
    def test_known_id_gets_its_name(self):
        assert parse_language("<sysLanguage>2</sysLanguage>") == LanguageSetting(
            id=2, name="Deutsch"
        )

    def test_unknown_id_keeps_the_id_without_a_name(self):
        assert parse_language("<sysLanguage>99</sysLanguage>") == LanguageSetting(
            id=99, name=None
        )

    def test_accepts_the_element_as_a_child(self):
        xml = "<root><sysLanguage>3</sysLanguage></root>"
        assert parse_language(xml) == LanguageSetting(id=3, name="English")

    @pytest.mark.parametrize(
        "xml",
        ["", "garbage", "<sysLanguage>x</sysLanguage>", "<other/>", "<sysLanguage/>"],
    )
    def test_unparsable_input_returns_none(self, xml):
        assert parse_language(xml) is None

    def test_xml_bomb_returns_none(self):
        bomb = (
            '<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]>'
            "<sysLanguage>&lol2;</sysLanguage>"
        )
        assert parse_language(bomb) is None


class TestParseClock:
    def test_full_sample(self):
        clock = parse_clock(CLOCK_XML)
        assert clock == ClockSetting(
            enabled=True,
            time_format="24h",
            timezone="Europe/Berlin",
            extra={"userOffsetMinute": "0", "userUtcTime": "0"},
        )

    def test_bare_clock_config_root_is_accepted(self):
        xml = '<clockConfig userEnable="false" timeFormat="TIME_FORMAT_12HOUR_ID"/>'
        clock = parse_clock(xml)
        assert clock is not None
        assert clock.enabled is False
        assert clock.time_format == "12h"
        assert clock.timezone is None

    def test_missing_user_enable_means_disabled(self):
        clock = parse_clock('<clockConfig timezoneInfo="UTC"/>')
        assert clock is not None
        assert clock.enabled is False

    def test_boolean_is_case_insensitive_and_garbage_is_null(self):
        assert parse_clock('<clockConfig userEnable="TRUE"/>').enabled is True
        assert parse_clock('<clockConfig userEnable="maybe"/>').enabled is None

    def test_unknown_time_format_is_null_but_kept_for_rewrite(self):
        clock = parse_clock('<clockConfig userEnable="true" timeFormat="WEIRD"/>')
        assert clock is not None
        assert clock.time_format is None
        assert clock.extra["timeFormat"] == "WEIRD"

    def test_unknown_attributes_are_preserved(self):
        clock = parse_clock('<clockConfig userEnable="true" brightnessLevel="3"/>')
        assert clock is not None
        assert clock.extra == {"brightnessLevel": "3"}

    @pytest.mark.parametrize("xml", ["", "nope", "<clockDisplay/>", "<other/>"])
    def test_unparsable_input_returns_none(self, xml):
        assert parse_clock(xml) is None


class TestParsePowerSaving:
    @pytest.mark.parametrize(
        ("text", "expected"), [("true", True), ("false", False), ("FALSE", False)]
    )
    def test_boolean(self, text, expected):
        xml = f"<systemtimeout><powersaving_enabled>{text}</powersaving_enabled></systemtimeout>"
        assert parse_power_saving(xml) == PowerSavingSetting(enabled=expected)

    def test_garbage_boolean_gives_null_field(self):
        xml = "<systemtimeout><powersaving_enabled>2</powersaving_enabled></systemtimeout>"
        assert parse_power_saving(xml) == PowerSavingSetting(enabled=None)

    @pytest.mark.parametrize("xml", ["", "x", "<systemtimeout/>"])
    def test_unparsable_input_returns_none(self, xml):
        assert parse_power_saving(xml) is None


class TestBuilders:
    def test_language(self):
        assert build_language_xml(12) == "<sysLanguage>12</sysLanguage>"

    def test_power_saving(self):
        assert build_power_saving_xml(True) == (
            "<systemtimeout><powersaving_enabled>true</powersaving_enabled></systemtimeout>"
        )
        assert "false" in build_power_saving_xml(False)

    def test_clock_enabled_writes_all_attributes_and_keeps_extras(self):
        from defusedxml import ElementTree

        xml = build_clock_xml(
            enabled=True,
            time_format="12h",
            timezone="Asia/Tokyo",
            extra={"userOffsetMinute": "0", "brightnessLevel": "3"},
        )
        config = ElementTree.fromstring(xml).find("clockConfig")
        assert config.attrib == {
            "userEnable": "true",
            "timeFormat": "TIME_FORMAT_12HOUR_ID",
            "timezoneInfo": "Asia/Tokyo",
            "userOffsetMinute": "0",
            "brightnessLevel": "3",
        }

    def test_clock_disabled_resends_the_values_read(self):
        from defusedxml import ElementTree

        xml = build_clock_xml(
            enabled=False,
            time_format="24h",
            timezone="Europe/Berlin",
            extra={"userUtcTime": "0"},
        )
        config = ElementTree.fromstring(xml).find("clockConfig")
        assert config.attrib["userEnable"] == "false"
        assert config.attrib["timeFormat"] == "TIME_FORMAT_24HOUR_ID"
        assert config.attrib["timezoneInfo"] == "Europe/Berlin"

    def test_values_are_escaped(self):
        from defusedxml import ElementTree

        xml = build_clock_xml(
            enabled=True,
            time_format="24h",
            timezone="UTC",
            extra={"note": 'a"b<c&d'},
        )
        assert (
            ElementTree.fromstring(xml).find("clockConfig").attrib["note"] == 'a"b<c&d'
        )


class TestTimezoneValidation:
    @pytest.mark.parametrize(
        "name", ["Europe/Berlin", "Asia/Tokyo", "UTC", "America/Argentina/Buenos_Aires"]
    )
    def test_accepts_iana_names(self, name):
        assert is_valid_timezone(name)

    @pytest.mark.parametrize(
        "name",
        [
            "Europe/Atlantis",
            "",
            "x" * 65,
            "CET-1CEST",
            "Factory",
            "posixrules",
            "localtime",
            'Europe/"Berlin',
            "Europe/<Berlin",
            "europe/berlin",
            None,
            5,
        ],
    )
    def test_rejects_everything_else(self, name):
        assert not is_valid_timezone(name)
