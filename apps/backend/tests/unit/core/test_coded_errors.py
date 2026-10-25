"""Tests for machine-readable error codes (additive ErrorDetail contract)."""

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from opencloudtouch.core.exception_handlers import (
    _validation_item,
    register_exception_handlers,
)
from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
    DiscoveryError,
    DomainValidationError,
    ErrorDetail,
    ExternalServiceError,
    OpenCloudTouchError,
    RadioConnectionError,
    RadioError,
    RadioTimeoutError,
    SSHConnectionError,
    SSHError,
    raise_coded,
    status_title,
)
from opencloudtouch.core.static_files import mount_static_files
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
)


class _Body(BaseModel):
    x: int

    @field_validator("x")
    @classmethod
    def _check(cls, v: int) -> int:
        if v < 0:
            raise ValueError("code:my_code")
        return v


class _ModelBody(BaseModel):
    a: int = 0

    @model_validator(mode="after")
    def _check(self):
        raise ValueError("code:model_level")


class _Plain(BaseModel):
    port: int


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/missing-device")
    async def missing_device():
        raise DeviceNotFoundError("abc")

    @app.post("/api/coded-field")
    async def coded_field(body: _Body):
        return {}

    @app.post("/api/coded-model")
    async def coded_model(body: _ModelBody):
        return {}

    @app.post("/api/plain")
    async def plain(body: _Plain):
        return {}

    @app.get("/api/conflict")
    async def conflict():
        raise_coded(409, "x_conflict", "msg", params={"a": 1}, extra={"ids": [1, 2]})

    @app.get("/api/conflict-field")
    async def conflict_field():
        raise_coded(409, "x_conflict", "msg", field="f")

    @app.get("/api/not-found-coded")
    async def not_found_coded():
        raise_coded(404, "x", "coded missing")

    @app.get("/api/domain")
    async def domain():
        raise DomainValidationError("m", field="f", code="c")

    @app.get("/api/domain-default")
    async def domain_default():
        raise DomainValidationError("m")

    @app.get("/api/boom")
    async def boom():
        raise RuntimeError("secret internals")

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=False)


def test_device_not_found_adds_code_params_extra(client):
    r = client.get("/api/missing-device")
    assert r.status_code == 404
    assert r.json() == {
        "type": "not_found",
        "title": "Device Not Found",
        "status": 404,
        "detail": "Device not found: abc",
        "instance": "/api/missing-device",
        "errors": None,
        "code": "device_not_found",
        "params": None,
        "extra": None,
    }


def test_invalid_body_adds_validation_code_and_path(client):
    r = client.post("/api/plain", json={"port": "abc"})
    body = r.json()
    assert r.status_code == 422
    assert body["code"] == "validation_error"
    assert body["type"] == "validation_error"
    assert body["title"] == "Invalid Request Data"
    assert body["detail"] == "Request validation failed"
    item = body["errors"][0]
    assert item["field"] == "body.port"
    assert item["path"] == "port"
    assert item["code"] == "validation_error"
    assert item["type"] == "int_parsing"
    assert "message" in item


def test_validator_code_convention_on_field(client):
    r = client.post("/api/coded-field", json={"x": -1})
    item = r.json()["errors"][0]
    assert item["field"] == "body.x"
    assert item["path"] == "x"
    assert item["code"] == "my_code"
    assert item["message"] == "Invalid value"
    assert "ctx" not in item


def test_model_level_validator_attributes_to_body(client):
    r = client.post("/api/coded-model", json={"a": 1})
    assert r.status_code == 422
    item = r.json()["errors"][0]
    assert item["field"] == "body"
    assert item["path"] == ""
    assert item["code"] == "model_level"


def test_raise_coded_builds_conflict_body(client):
    r = client.get("/api/conflict")
    body = r.json()
    assert r.status_code == 409
    assert body["type"] == "conflict"
    assert body["title"] == "Conflict"
    assert body["detail"] == "msg"
    assert body["code"] == "x_conflict"
    assert body["params"] == {"a": "1"}
    assert body["extra"] == {"ids": [1, 2]}
    assert body["instance"] == "/api/conflict"
    assert body["errors"] is None


def test_raise_coded_with_field_adds_error_item(client):
    r = client.get("/api/conflict-field")
    assert r.json()["errors"] == [
        {
            "field": "f",
            "path": "f",
            "message": "msg",
            "type": None,
            "code": "x_conflict",
        }
    ]


def test_domain_validation_error_with_code_and_field(client):
    r = client.get("/api/domain")
    body = r.json()
    assert r.status_code == 400
    assert body["code"] == "c"
    assert body["errors"][0]["path"] == "f"
    assert body["errors"][0]["type"] == "domain_validation_error"
    assert body["errors"][0]["code"] == "c"


def test_domain_validation_error_default_code(client):
    r = client.get("/api/domain-default")
    assert r.status_code == 400
    assert r.json()["code"] == "validation_error"
    assert r.json()["errors"] is None


def test_unhandled_exception_has_internal_error_code(client):
    r = client.get("/api/boom")
    body = r.json()
    assert r.status_code == 500
    assert body["code"] == "internal_error"
    assert body["detail"] == "An unexpected error occurred. Please try again later."
    assert "secret" not in json.dumps(body)


def test_unknown_api_route_without_dist_has_not_found_code(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"
    assert r.json()["type"] == "not_found"


def test_http_exception_non_404_has_null_code():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/teapot")
    async def teapot():
        raise HTTPException(status_code=418, detail="teapot")

    r = TestClient(app).get("/api/teapot")
    assert r.json()["code"] is None
    assert r.json()["detail"] == "teapot"


@pytest.fixture
def client_with_dist(tmp_path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")
    app = _build_app()
    mount_static_files(app, tmp_path)
    return TestClient(app, raise_server_exceptions=False)


def test_coded_404_not_overwritten_by_spa_fallback(client_with_dist):
    r = client_with_dist.get("/api/not-found-coded")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["code"] == "x"
    assert r.json()["detail"] == "coded missing"


def test_unknown_api_route_with_dist_has_not_found_code(client_with_dist):
    r = client_with_dist.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"
    assert set(r.json()) >= {"code", "params", "extra", "errors"}


def test_spa_route_still_serves_index(client_with_dist):
    r = client_with_dist.get("/some/page")
    assert r.status_code == 200
    assert "spa" in r.text


# ---------------------------------------------------------------------------
# AC 8: one parametrised test over every handler registered in
# register_exception_handlers, driven through real requests
# ---------------------------------------------------------------------------

_GENERIC_500 = "An unexpected error occurred. Please try again later."
_RADIO_TIMEOUT = "Radio station search timed out. Please try again."
_RADIO_DOWN = "Radio station search is temporarily unavailable. Please try again later."

# exception class -> (instance, status, type, title, detail, expected code)
# title/detail/type/status are the values the handlers returned BEFORE codes were added.
_CASES = {
    StarletteHTTPException: (
        StarletteHTTPException(404, "Not Found"),
        404,
        "not_found",
        "Not Found",
        "Not Found",
        "not_found",
    ),
    HTTPException: (
        HTTPException(404, "gone"),
        404,
        "not_found",
        "gone",
        "gone",
        "not_found",
    ),
    DeviceNotFoundError: (
        DeviceNotFoundError("d1"),
        404,
        "not_found",
        "Device Not Found",
        "Device not found: d1",
        "device_not_found",
    ),
    DeviceConnectionError: (
        DeviceConnectionError("1.2.3.4"),
        503,
        "service_unavailable",
        "Device Unavailable",
        "Device unreachable: 1.2.3.4",
        "device_unreachable",
    ),
    DiscoveryError: (
        DiscoveryError("x"),
        500,
        "server_error",
        "Device Discovery Failed",
        "x",
        "internal_error",
    ),
    DomainValidationError: (
        DomainValidationError("bad"),
        400,
        "bad_request",
        "Validation Error",
        "bad",
        "validation_error",
    ),
    RadioTimeoutError: (
        RadioTimeoutError("t"),
        504,
        "gateway_timeout",
        "Radio Service Timeout",
        _RADIO_TIMEOUT,
        None,
    ),
    RadioConnectionError: (
        RadioConnectionError("c"),
        503,
        "service_unavailable",
        "Radio Service Unavailable",
        _RADIO_DOWN,
        None,
    ),
    RadioError: (
        RadioError("r"),
        500,
        "server_error",
        "Radio Service Error",
        "r",
        None,
    ),
    RadioBrowserTimeoutError: (
        RadioBrowserTimeoutError("t"),
        504,
        "gateway_timeout",
        "Radio Service Timeout",
        _RADIO_TIMEOUT,
        None,
    ),
    RadioBrowserConnectionError: (
        RadioBrowserConnectionError("c"),
        503,
        "service_unavailable",
        "Radio Service Unavailable",
        _RADIO_DOWN,
        None,
    ),
    RadioBrowserError: (
        RadioBrowserError("e"),
        503,
        "service_unavailable",
        "Radio Service Unavailable",
        _RADIO_DOWN,
        None,
    ),
    SSHConnectionError: (
        SSHConnectionError("1.2.3.4"),
        503,
        "service_unavailable",
        "SSH Connection Failed",
        "SSH connection refused: 1.2.3.4",
        None,
    ),
    SSHError: (
        SSHError("1.2.3.4"),
        500,
        "server_error",
        "SSH Operation Failed",
        "SSH operation failed: 1.2.3.4",
        None,
    ),
    ExternalServiceError: (
        ExternalServiceError("e"),
        502,
        "bad_gateway",
        "External Service Error",
        "e",
        None,
    ),
    OpenCloudTouchError: (
        OpenCloudTouchError("o"),
        500,
        "server_error",
        "Internal Error",
        "o",
        "internal_error",
    ),
    Exception: (
        RuntimeError("boom"),
        500,
        "server_error",
        "Internal Server Error",
        _GENERIC_500,
        "internal_error",
    ),
}


def _registered_handler_classes() -> set:
    app = FastAPI()
    register_exception_handlers(app)
    return set(app.exception_handlers) - {
        RequestValidationError,
        WebSocketRequestValidationError,  # FastAPI default
        CodedApiError,  # covered by the raise_coded tests
    }


def test_case_table_covers_every_registered_handler():
    assert _registered_handler_classes() == set(_CASES)


@pytest.mark.parametrize(
    "exc_cls",
    sorted(_CASES, key=lambda c: c.__module__ + c.__qualname__),
    ids=lambda c: f"{c.__module__}.{c.__qualname__}",
)
def test_every_handler_keeps_old_values_and_adds_new_keys(exc_cls):
    exc, status, type_, title, detail, code = _CASES[exc_cls]
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/x")
    async def raiser():
        raise exc

    response = TestClient(app, raise_server_exceptions=False).get("/api/x")
    body = response.json()

    assert response.status_code == status
    assert body["status"] == status
    assert body["type"] == type_
    assert body["title"] == title
    assert body["detail"] == detail
    assert body["instance"] == "/api/x"
    assert body["errors"] is None
    assert body["code"] == code
    assert "params" in body
    assert body["params"] is None
    assert "extra" in body
    assert body["extra"] is None


def test_request_validation_error_keeps_old_values_and_adds_path_and_code(client):
    body = client.post("/api/plain", json={"port": "abc"}).json()
    item = body["errors"][0]
    assert body["title"] == "Invalid Request Data"
    assert body["detail"] == "Request validation failed"
    assert item["field"] == "body.port"
    assert item["type"] == "int_parsing"
    assert (
        item["message"]
        == "Input should be a valid integer, unable to parse string as an integer"
    )
    assert item["path"] == "port"
    assert item["code"] == "validation_error"


def test_validation_item_without_ctx_falls_back_to_msg_prefix():
    item = _validation_item(
        {
            "type": "value_error",
            "loc": ("body", "x"),
            "msg": "Value error, code:my_code",
        }
    )
    assert item.code == "my_code"
    assert item.message == "Invalid value"
    assert item.path == "x"


def test_validation_item_value_error_without_code_convention():
    item = _validation_item(
        {"type": "value_error", "loc": ("query", "n"), "msg": "Value error, too small"}
    )
    assert item.code == "validation_error"
    assert item.message == "Value error, too small"
    assert item.path == "n"


def test_error_detail_model_defaults():
    dumped = ErrorDetail(type="t", title="T", status=400, detail="d").model_dump()
    assert dumped["code"] is None
    assert dumped["params"] is None
    assert dumped["extra"] is None


def test_status_title_defaults_and_fallback():
    assert status_title(409) == "Conflict"
    assert status_title(418) == "HTTP 418"


# ---------------------------------------------------------------------------
# raise_coded hardening: 5xx detail, extra serialisation, code pattern
# ---------------------------------------------------------------------------


def _coded_app(*, status: int, detail: str, **kwargs) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/coded")
    async def coded():
        raise_coded(status, "x_failed", detail, **kwargs)

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_raise_coded_5xx_replaces_detail_with_generic_text(status, caplog):
    client = _coded_app(
        status=status, detail="failed: /etc/secret raised ValueError", field="f"
    )
    with caplog.at_level("ERROR"):
        response = client.get("/api/coded")
    body = response.json()

    assert response.status_code == status
    assert body["code"] == "x_failed"
    assert body["detail"] == _GENERIC_500
    assert body["errors"][0]["message"] == _GENERIC_500
    assert "/etc/secret" not in json.dumps(body)
    assert "/etc/secret" in caplog.text


def test_raise_coded_4xx_keeps_detail():
    response = _coded_app(status=409, detail="exact reason").get("/api/coded")
    assert response.json()["detail"] == "exact reason"


def test_raise_coded_serialises_extra_with_json_encoder():
    when = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    response = _coded_app(status=409, detail="d", extra={"at": when}).get("/api/coded")
    assert response.status_code == 409
    assert response.json()["extra"] == {"at": "2026-06-01T12:00:00+00:00"}


def test_raise_coded_non_serialisable_extra_still_returns_error_detail(caplog):
    with caplog.at_level("WARNING"):
        response = _coded_app(status=409, detail="d", extra={"x": object()}).get(
            "/api/coded"
        )
    body = response.json()
    assert response.status_code == 409
    assert body["code"] == "x_failed"
    assert body["extra"] is None


@pytest.mark.parametrize("bad", ["Bad-Code", "1code", "", "with space", "UPPER"])
def test_raise_coded_rejects_invalid_code_pattern(bad):
    with pytest.raises(ValueError, match="invalid error code"):
        raise_coded(409, bad, "msg")


def test_domain_validation_error_rejects_invalid_code_pattern():
    with pytest.raises(ValueError, match="invalid error code"):
        DomainValidationError("m", code="Bad Code")
