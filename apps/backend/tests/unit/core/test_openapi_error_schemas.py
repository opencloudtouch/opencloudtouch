"""ErrorDetail/ErrorItem must be part of the generated OpenAPI schema (A.4)."""

from opencloudtouch.main import app


def _schemas() -> dict:
    app.openapi_schema = None
    return app.openapi()["components"]["schemas"]


def test_error_detail_schema_has_new_optional_fields():
    props = _schemas()["ErrorDetail"]["properties"]
    for key in ("type", "title", "status", "detail", "instance", "errors"):
        assert key in props
    for key in ("code", "params", "extra"):
        assert key in props
    required = _schemas()["ErrorDetail"].get("required", [])
    assert not {"code", "params", "extra"} & set(required)


def test_error_item_schema_has_path_and_code():
    schema = _schemas()["ErrorItem"]
    assert {"field", "path", "message", "type", "code"} <= set(schema["properties"])
    assert schema["required"] == ["field", "message"] or set(schema["required"]) == {
        "field",
        "message",
    }


def test_success_schemas_unchanged_and_openapi_still_builds():
    spec = app.openapi()
    assert "/api/devices/discover" in spec["paths"]
