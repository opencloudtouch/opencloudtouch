"""Route tests for the Marge stereo pair group endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_stereo_pair_service
from opencloudtouch.main import app
from opencloudtouch.stereo_pairs.repository import DeviceAlreadyPairedError, StereoPair
from opencloudtouch.stereo_pairs.service import UnknownDeviceError
from opencloudtouch.stereo_pairs.xml import build_group_xml

BODY = (
    b"<group><masterDeviceId>L1</masterDeviceId><name>Office</name><roles>"
    b"<groupRole><deviceId>L1</deviceId><role>LEFT</role></groupRole>"
    b"<groupRole><deviceId>R1</deviceId><role>RIGHT</role></groupRole>"
    b"</roles></group>"
)
GROUP = "/streaming/account/123/group/"
DEVICE_GROUP = "/streaming/account/123/device/{}/group/"


def _pair(pair_id=7):
    return StereoPair(pair_id, "Office", "L1", "L1", "R1", datetime.now(UTC))


@pytest.fixture
def service():
    mock = MagicMock()
    for name in ("marge_create", "get_for_device", "marge_rename", "marge_dissolve"):
        setattr(mock, name, AsyncMock())
    app.dependency_overrides[get_stereo_pair_service] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_stereo_pair_service, None)


@pytest.fixture
def client():
    return TestClient(app)


class TestCreateGroup:
    def test_created_returns_201_with_group_id(self, client, service):
        service.marge_create.return_value = _pair()

        response = client.post(GROUP, content=BODY)

        assert response.status_code == 201
        assert (
            "application/vnd.bose.streaming-v1.2+xml"
            in response.headers["content-type"]
        )
        assert '<group id="7">' in response.text
        assert "<role>LEFT</role>" in response.text
        assert "<role>RIGHT</role>" in response.text
        request = service.marge_create.call_args.args[0]
        assert (request.left_device_id, request.right_device_id) == ("L1", "R1")

    def test_works_without_trailing_slash(self, client, service):
        service.marge_create.return_value = _pair()

        assert (
            client.post("/streaming/account/123/group", content=BODY).status_code == 201
        )

    def test_device_already_in_group_is_4041(self, client, service):
        service.marge_create.side_effect = DeviceAlreadyPairedError("L1")

        response = client.post(GROUP, content=BODY)

        assert response.status_code == 400
        assert "<status-code>4041</status-code>" in response.text

    def test_malformed_body_is_400(self, client, service):
        response = client.post(GROUP, content=b"nonsense")

        assert response.status_code == 400
        assert "<status-code>4000</status-code>" in response.text
        service.marge_create.assert_not_called()


class TestGetDeviceGroup:
    def test_member_gets_group(self, client, service):
        service.get_for_device.return_value = _pair()

        response = client.get(DEVICE_GROUP.format("R1"))

        assert response.status_code == 200
        assert '<group id="7">' in response.text

    def test_not_in_group_gets_empty_group(self, client, service):
        service.get_for_device.return_value = None

        response = client.get(DEVICE_GROUP.format("R1"))

        assert response.status_code == 200
        assert response.text.endswith("<group/>")

    def test_unknown_device_is_4012(self, client, service):
        service.get_for_device.side_effect = UnknownDeviceError("NOPE")

        response = client.get(DEVICE_GROUP.format("NOPE"))

        assert response.status_code == 400
        assert "<status-code>4012</status-code>" in response.text


class TestUpdateAndDelete:
    def test_put_renames(self, client, service):
        service.marge_rename.return_value = _pair()

        response = client.put("/streaming/account/123/group/7", content=BODY)

        assert response.status_code == 200
        service.marge_rename.assert_awaited_once_with(7, "Office")

    def test_put_unknown_group_is_error(self, client, service):
        service.marge_rename.return_value = None

        assert (
            client.put("/streaming/account/123/group/7", content=BODY).status_code
            == 400
        )

    def test_delete_is_idempotent_success(self, client, service):
        response = client.delete("/streaming/account/123/group/7")

        assert response.status_code == 200
        assert "<status>Group deleted successfully</status>" in response.text
        service.marge_dissolve.assert_awaited_once_with(7)

    def test_post_renames_like_put(self, client, service):
        service.marge_rename.return_value = _pair()

        response = client.post("/streaming/account/123/group/7", content=BODY)

        assert response.status_code == 200
        service.marge_rename.assert_awaited_once_with(7, "Office")

    @pytest.mark.parametrize("path", ["/group/", "/group"])
    def test_teardown_without_id_is_acknowledged(self, client, service, path):
        response = client.delete("/streaming/account/123" + path)

        assert response.status_code == 200
        assert "<status>Group teardown acknowledged</status>" in response.text
        service.marge_dissolve.assert_not_awaited()

    def test_group_xml_lists_name_before_master(self):
        xml = build_group_xml(_pair()).decode()

        assert xml.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
        assert xml.index("<name>") < xml.index("<masterDeviceId>")


def test_provider_settings_match_reference_servers(client):
    response = client.get("/streaming/account/123/provider_settings")

    assert response.status_code == 200
    assert "<boseId>123</boseId>" in response.text
    assert "<keyName>STREAMING_QUALITY</keyName>" in response.text
