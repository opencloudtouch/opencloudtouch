"""BoseDeviceClientAdapter: language, clock and power saving over a fake transport."""

from unittest.mock import patch

import httpx
import pytest

from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceRejectedError
from opencloudtouch.devices.client import (
    ClockSetting,
    LanguageSetting,
    PowerSavingSetting,
)
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter

CLOCK_XML = (
    '<clockDisplay><clockConfig userEnable="true" timeFormat="TIME_FORMAT_24HOUR_ID" '
    'timezoneInfo="Europe/Berlin" userOffsetMinute="0" userUtcTime="0"/></clockDisplay>'
)
POWER_XML = (
    "<systemtimeout><powersaving_enabled>true</powersaving_enabled></systemtimeout>"
)


@pytest.fixture
def transport(monkeypatch):
    """Route every httpx.AsyncClient of the adapter to a recording MockTransport."""
    real_client = httpx.AsyncClient
    state: dict = {"requests": [], "routes": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        route = state["routes"].get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404)
        if isinstance(route, Exception):
            raise route
        return route

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(
        "opencloudtouch.devices.client_adapter.httpx.AsyncClient", factory
    )
    return state


@pytest.fixture
def adapter():
    with patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"), patch(
        "opencloudtouch.devices.client_adapter.BoseClient"
    ):
        return BoseDeviceClientAdapter("http://192.168.1.100:8090")


class TestReads:
    @pytest.mark.asyncio
    async def test_all_three_sample_responses(self, adapter, transport):
        transport["routes"] = {
            ("GET", "/language"): httpx.Response(
                200, text="<sysLanguage>2</sysLanguage>"
            ),
            ("GET", "/clockDisplay"): httpx.Response(200, text=CLOCK_XML),
            ("GET", "/systemtimeout"): httpx.Response(200, text=POWER_XML),
        }

        assert await adapter.get_language() == LanguageSetting(2, "Deutsch")
        assert await adapter.get_clock() == ClockSetting(
            True, "24h", "Europe/Berlin", {"userOffsetMinute": "0", "userUtcTime": "0"}
        )
        assert await adapter.get_power_saving() == PowerSavingSetting(True)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [400, 404, 500, 503])
    async def test_error_statuses_yield_none(self, adapter, transport, status):
        transport["routes"] = {("GET", "/clockDisplay"): httpx.Response(status)}
        assert await adapter.get_clock() is None

    @pytest.mark.asyncio
    async def test_garbage_body_yields_none(self, adapter, transport):
        transport["routes"] = {
            ("GET", "/clockDisplay"): httpx.Response(200, text="<<<")
        }
        assert await adapter.get_clock() is None

    @pytest.mark.asyncio
    async def test_timeout_yields_none(self, adapter, transport):
        transport["routes"] = {
            ("GET", "/clockDisplay"): httpx.ReadTimeout("slow", request=None)
        }
        assert await adapter.get_clock() is None

    @pytest.mark.asyncio
    async def test_refused_connection_raises_device_connection_error(
        self, adapter, transport
    ):
        transport["routes"] = {
            ("GET", "/language"): httpx.ConnectError("refused", request=None)
        }
        with pytest.raises(DeviceConnectionError):
            await adapter.get_language()

    @pytest.mark.asyncio
    async def test_non_404_failure_is_logged_without_url_or_body(
        self, adapter, transport, caplog
    ):
        transport["routes"] = {("GET", "/language"): httpx.Response(500, text="SECRET")}
        with caplog.at_level("WARNING"):
            await adapter.get_language()
        assert "/language" in caplog.text
        assert "500" in caplog.text
        assert "SECRET" not in caplog.text
        assert "192.168.1.100" not in caplog.text

    @pytest.mark.asyncio
    async def test_404_is_not_logged_as_warning(self, adapter, transport, caplog):
        with caplog.at_level("WARNING"):
            await adapter.get_language()
        assert caplog.text == ""


class TestWrites:
    @pytest.mark.asyncio
    async def test_set_language_posts_xml(self, adapter, transport):
        transport["routes"] = {("POST", "/language"): httpx.Response(200)}

        await adapter.set_language(12)

        request = transport["requests"][-1]
        assert request.method == "POST"
        assert request.content == b"<sysLanguage>12</sysLanguage>"
        assert request.headers["content-type"] == "application/xml"

    @pytest.mark.asyncio
    async def test_set_clock_posts_all_attributes(self, adapter, transport):
        from defusedxml import ElementTree

        transport["routes"] = {("POST", "/clockDisplay"): httpx.Response(200)}

        await adapter.set_clock(
            True, "12h", "Asia/Tokyo", {"userOffsetMinute": "0", "brightnessLevel": "3"}
        )

        config = ElementTree.fromstring(transport["requests"][-1].content).find(
            "clockConfig"
        )
        assert config.attrib == {
            "userEnable": "true",
            "timeFormat": "TIME_FORMAT_12HOUR_ID",
            "timezoneInfo": "Asia/Tokyo",
            "userOffsetMinute": "0",
            "brightnessLevel": "3",
        }

    @pytest.mark.asyncio
    async def test_set_power_saving_posts_xml(self, adapter, transport):
        transport["routes"] = {("POST", "/systemtimeout"): httpx.Response(200)}

        await adapter.set_power_saving(True)

        assert transport["requests"][-1].content == POWER_XML.encode()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [400, 404, 500])
    async def test_http_error_on_post_is_device_rejected(
        self, adapter, transport, status
    ):
        transport["routes"] = {("POST", "/language"): httpx.Response(status)}

        with pytest.raises(DeviceRejectedError) as excinfo:
            await adapter.set_language(2)

        assert excinfo.value.status_code == status

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            httpx.ConnectError("refused", request=None),
            httpx.ReadTimeout("slow", request=None),
        ],
    )
    async def test_connection_errors_on_post_are_not_rejections(
        self, adapter, transport, error
    ):
        transport["routes"] = {("POST", "/language"): error}

        with pytest.raises(DeviceConnectionError) as excinfo:
            await adapter.set_language(2)

        assert not isinstance(excinfo.value, DeviceRejectedError)
