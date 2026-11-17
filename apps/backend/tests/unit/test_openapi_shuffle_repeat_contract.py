"""OpenAPI contract for shuffle/repeat answers (AC-B11).

The response schemas of GET .../now-playing and POST .../key are documented
as named models. The change is additive: existing fields stay required and
no status code is removed.
"""

from pathlib import Path

import pytest
import yaml

SPEC_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"


@pytest.fixture(scope="module")
def spec():
    with open(SPEC_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _schemas(spec):
    return spec["components"]["schemas"]


def _ref_name(response):
    return response["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]


def _allows_null(prop):
    return {"type": "null"} in prop.get("anyOf", [])


def test_now_playing_response_schema_has_nullable_setting_fields(spec):
    props = _schemas(spec)["NowPlayingResponse"]["properties"]

    for field in ("shuffle_setting", "repeat_setting"):
        assert {"type": "string"} in props[field]["anyOf"]
        assert _allows_null(props[field])


def test_now_playing_response_keeps_existing_fields_required_or_optional(spec):
    props = _schemas(spec)["NowPlayingResponse"]["properties"]

    for field in (
        "source",
        "state",
        "station_name",
        "artist",
        "track",
        "album",
        "artwork_url",
        "content_location",
        "item_name",
        "skip_enabled",
        "online",
    ):
        assert field in props, f"missing existing field {field}"


def test_key_press_response_has_optional_nullable_settings(spec):
    schema = _schemas(spec)["KeyPressResponse"]

    assert set(schema["required"]) == {"message", "device_id"}
    for field in ("shuffle_setting", "repeat_setting"):
        assert field in schema["properties"]
        assert field not in schema["required"]
        assert _allows_null(schema["properties"][field])


def test_now_playing_path_answers_with_named_model(spec):
    response = spec["paths"]["/api/devices/{device_id}/now-playing"]["get"][
        "responses"
    ]["200"]

    assert _ref_name(response) == "NowPlayingResponse"


def test_key_path_answers_with_named_model_and_keeps_422(spec):
    operation = spec["paths"]["/api/devices/{device_id}/key"]["post"]

    assert _ref_name(operation["responses"]["200"]) == "KeyPressResponse"
    assert "422" in operation["responses"]
