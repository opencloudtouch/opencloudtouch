"""Tests for machine-readable error codes (additive ErrorDetail contract)."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from opencloudtouch.core import exception_handlers
from opencloudtouch.core.exception_handlers import register_exception_handlers
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
# AC 8: one parametrised test over every registered handler
# ---------------------------------------------------------------------------

# exception class -> (instance, status, type, expected code)
_CASES = {
    StarletteHTTPException: (
        StarletteHTTPException(404, "Not Found"),
        404,
        "not_found",
        "not_found",
    ),
    HTTPException: (HTTPException(404, "gone"), 404, "not_found", "not_found"),
    DeviceNotFoundError: (
        DeviceNotFoundError("d1"),
        404,
        "not_found",
        "device_not_found",
    ),
    DeviceConnectionError: (
        DeviceConnectionError("1.2.3.4"),
        503,
        "service_unavailable",
        "device_unreachable",
    ),
    DiscoveryError: (DiscoveryError("x"), 500, "server_error", "internal_error"),
    DomainValidationError: (
        DomainValidationError("bad"),
        400,
        "bad_request",
        "validation_error",
    ),
    RadioTimeoutError: (RadioTimeoutError("t"), 504, "gateway_timeout", None),
    RadioConnectionError: (RadioConnectionError("c"), 503, "service_unavailable", None),
    RadioError: (RadioError("r"), 500, "server_error", None),
    RadioBrowserTimeoutError: (
        RadioBrowserTimeoutError("t"),
        504,
        "gateway_timeout",
        None,
    ),
    RadioBrowserConnectionError: (
        RadioBrowserConnectionError("c"),
        503,
        "service_unavailable",
        None,
    ),
    RadioBrowserError: (RadioBrowserError("e"), 503, "service_unavailable", None),
    SSHConnectionError: (
        SSHConnectionError("1.2.3.4"),
        503,
        "service_unavailable",
        None,
    ),
    SSHError: (SSHError("1.2.3.4"), 500, "server_error", None),
    ExternalServiceError: (ExternalServiceError("e"), 502, "bad_gateway", None),
    OpenCloudTouchError: (
        OpenCloudTouchError("o"),
        500,
        "server_error",
        "internal_error",
    ),
    Exception: (RuntimeError("boom"), 500, "server_error", "internal_error"),
}


def _registered_handlers() -> dict:
    app = FastAPI()
    register_exception_handlers(app)
    return {
        k: v
        for k, v in app.exception_handlers.items()
        if k
        not in (
            RequestValidationError,
            WebSocketRequestValidationError,  # FastAPI default
            CodedApiError,
        )
    }


def test_case_table_covers_every_registered_handler():
    assert set(_registered_handlers()) == set(_CASES)


@pytest.mark.parametrize(
    "exc_cls",
    sorted(_CASES, key=lambda c: c.__module__ + c.__qualname__),
    ids=lambda c: f"{c.__module__}.{c.__qualname__}",
)
def test_every_handler_keeps_old_keys_and_adds_new(exc_cls):
    exc, status, type_, code = _CASES[exc_cls]
    handler = _registered_handlers()[exc_cls]
    req = MagicMock()
    req.url.path = "/api/x"

    response = _run(handler(req, exc))
    body = json.loads(response.body.decode())

    assert response.status_code == status
    assert body["status"] == status
    assert body["type"] == type_
    assert body["instance"] == "/api/x"
    assert {"title", "detail", "errors"} <= set(body)
    assert body["code"] == code
    assert "params" in body
    assert body["params"] is None
    assert "extra" in body
    assert body["extra"] is None


def test_request_validation_handler_present_and_additive():
    handler = exception_handlers.validation_exception_handler
    req = MagicMock()
    req.url.path = "/api/x"
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "a", "b"),
                "msg": "Field required",
                "input": {},
            }
        ]
    )
    body = json.loads(_run(handler(req, exc)).body.decode())
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == "body.a.b"
    assert body["errors"][0]["path"] == "a.b"
    assert body["errors"][0]["message"] == "Field required"
    assert body["errors"][0]["type"] == "missing"


def test_error_detail_model_defaults():
    d = ErrorDetail(type="t", title="T", status=400, detail="d")
    dumped = d.model_dump()
    assert dumped["code"] is None
    assert dumped["params"] is None
    assert dumped["extra"] is None


def _run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)


def test_status_title_defaults_and_fallback():
    from opencloudtouch.core.exceptions import status_title

    assert status_title(409) == "Conflict"
    assert status_title(418) == "HTTP 418"
