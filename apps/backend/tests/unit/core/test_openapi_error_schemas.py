"""ErrorDetail/ErrorItem must be part of the generated OpenAPI schema (A.4)."""

import pytest
from fastapi import FastAPI

from opencloudtouch.core.openapi import install_error_schemas


@pytest.fixture
def schemas() -> dict:
    """Schemas of a fresh app, so the global application schema is never mutated."""
    app = FastAPI()
    install_error_schemas(app)
    return app.openapi()["components"]["schemas"]


def test_error_detail_schema_has_new_optional_fields(schemas):
    schema = schemas["ErrorDetail"]
    for key in ("type", "title", "status", "detail", "instance", "errors"):
        assert key in schema["properties"]
    for key in ("code", "params", "extra"):
        assert key in schema["properties"]
        assert key not in schema.get("required", [])


def test_error_item_schema_has_path_and_code(schemas):
    schema = schemas["ErrorItem"]
    assert {"field", "path", "message", "type", "code"} <= set(schema["properties"])
    assert set(schema["required"]) == {"field", "message"}


def test_error_detail_references_error_item(schemas):
    errors = schemas["ErrorDetail"]["properties"]["errors"]
    assert "ErrorItem" in str(errors)


def _add_ping(app: FastAPI) -> FastAPI:
    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_success_schemas_are_untouched():
    plain = _add_ping(FastAPI())
    patched = FastAPI()
    install_error_schemas(patched)
    _add_ping(patched)

    assert patched.openapi()["paths"] == plain.openapi()["paths"]


def test_application_schema_publishes_error_models():
    from opencloudtouch.main import app

    names = set(app.openapi()["components"]["schemas"])
    assert {"ErrorDetail", "ErrorItem", "HealthResponse"} <= names
