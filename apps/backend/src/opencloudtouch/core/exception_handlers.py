"""
RFC 7807-inspired standardized exception handlers for OpenCloudTouch.

All domain and HTTP exceptions are mapped to a consistent ErrorDetail response
format. Register them all via ``register_exception_handlers(app)``.
"""

import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
    DiscoveryError,
    DomainValidationError,
    ErrorDetail,
    ErrorItem,
    ExternalServiceError,
    OpenCloudTouchError,
    RadioConnectionError,
    RadioError,
    RadioTimeoutError,
    SSHConnectionError,
    SSHError,
    map_status_to_type,
    status_title,
)
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
)

logger = logging.getLogger(__name__)


def _make_domain_handler(
    *,
    status_code: int,
    error_type: str,
    title: str,
    detail: str | None = None,
    log_level: str = "error",
    exc_info: bool = False,
    code: str | None = None,
) -> Callable[[Request, Any], Coroutine[Any, Any, JSONResponse]]:
    """Factory for domain exception handlers that follow the same pattern.

    Args:
        status_code: HTTP status code for the response.
        error_type: RFC 7807 error type string.
        title: Human-readable error title.
        detail: Fixed detail message. If None, uses str(exc).
        log_level: Logging level ("warning", "error").
        exc_info: Whether to include exception traceback in log.
        code: Stable machine-readable error code (None for uncoded errors).
    """
    log_fn = getattr(logger, log_level)

    async def handler(request: Request, exc: Exception) -> JSONResponse:  # NOSONAR
        log_fn("%s: %s", title, exc, exc_info=exc if exc_info else False)
        return JSONResponse(
            status_code=status_code,
            content=ErrorDetail(
                type=error_type,
                title=title,
                status=status_code,
                detail=detail or str(exc),
                instance=str(request.url.path),
                code=code,
            ).model_dump(),
        )

    return handler


def _not_found_code(status_code: int) -> str | None:
    return error_codes.NOT_FOUND if status_code == 404 else None


def _error_path(loc: tuple[Any, ...] | list[Any]) -> str:
    """Drop a leading body/query/path/header segment and join the rest with '.'."""
    parts = [str(part) for part in loc]
    if parts and parts[0] in ("body", "query", "path", "header"):
        parts = parts[1:]
    return ".".join(parts)


_CODE_PREFIX = re.compile(r"^code:([a-z][a-z0-9_]*)$")


def _validation_item(err: dict[str, Any]) -> ErrorItem:
    """Build an ErrorItem from a Pydantic error, honouring ``ValueError("code:x")``."""
    code = error_codes.VALIDATION_ERROR
    message = err["msg"]
    if err["type"] == "value_error":
        ctx_error = (err.get("ctx") or {}).get("error")
        raw = str(ctx_error) if ctx_error is not None else message
        raw = raw.removeprefix("Value error, ")
        match = _CODE_PREFIX.match(raw)
        if match:
            code = match.group(1)
            message = "Invalid value"
    return ErrorItem(
        field=".".join(str(loc) for loc in err["loc"]),
        path=_error_path(err["loc"]),
        message=message,
        type=err["type"],
        code=code,
    )


async def coded_api_error_handler(request: Request, exc: CodedApiError) -> JSONResponse:
    """Render a ``CodedApiError`` (``raise_coded``) as ``ErrorDetail``."""
    if exc.status_code >= 500:
        logger.error("%s: %s", exc.code, exc.detail, exc_info=exc)
    else:
        logger.warning("%s: %s", exc.code, exc.detail)
    errors = None
    if exc.field:
        errors = [
            ErrorItem(
                field=exc.field,
                path=exc.field,
                message=exc.detail,
                code=exc.code,
            )
        ]
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(
            type=map_status_to_type(exc.status_code),
            title=exc.title or status_title(exc.status_code),
            status=exc.status_code,
            detail=exc.detail,
            instance=str(request.url.path),
            errors=errors,
            code=exc.code,
            params=(
                {str(k): str(v) for k, v in exc.params.items()}
                if exc.params is not None
                else None
            ),
            extra=exc.extra,
        ).model_dump(),
    )


async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle Starlette HTTPException (404, 405 from routing layer) with RFC 7807 format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(
            type=map_status_to_type(exc.status_code),
            title=exc.detail or f"HTTP {exc.status_code}",
            status=exc.status_code,
            detail=exc.detail or f"HTTP {exc.status_code} error",
            instance=str(request.url.path),
            code=_not_found_code(exc.status_code),
        ).model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException with standardized error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(
            type=map_status_to_type(exc.status_code),
            title=exc.detail,
            status=exc.status_code,
            detail=exc.detail,
            instance=str(request.url.path),
            code=_not_found_code(exc.status_code),
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with field-level details."""
    return JSONResponse(
        status_code=422,
        content=ErrorDetail(
            type="validation_error",
            title="Invalid Request Data",
            status=422,
            detail="Request validation failed",
            instance=str(request.url.path),
            errors=[_validation_item(err) for err in exc.errors()],
            code=error_codes.VALIDATION_ERROR,
        ).model_dump(),
    )


async def device_not_found_handler(
    request: Request, exc: DeviceNotFoundError
) -> JSONResponse:
    """Handle DeviceNotFoundError as 404 HTTP response."""
    logger.warning("Device not found: %s", exc.device_id)
    return JSONResponse(
        status_code=404,
        content=ErrorDetail(
            type="not_found",
            title="Device Not Found",
            status=404,
            detail=str(exc),
            instance=str(request.url.path),
            code=error_codes.DEVICE_NOT_FOUND,
        ).model_dump(),
    )


device_connection_error_handler = _make_domain_handler(
    status_code=503,
    error_type="service_unavailable",
    title="Device Unavailable",
    exc_info=True,
    code=error_codes.DEVICE_UNREACHABLE,
)

discovery_error_handler = _make_domain_handler(
    status_code=500,
    error_type="server_error",
    title="Device Discovery Failed",
    exc_info=True,
    code=error_codes.INTERNAL_ERROR,
)

oct_error_handler = _make_domain_handler(
    status_code=500,
    error_type="server_error",
    title="Internal Error",
    exc_info=True,
    code=error_codes.INTERNAL_ERROR,
)

radio_browser_timeout_handler = _make_domain_handler(
    status_code=504,
    error_type="gateway_timeout",
    title="Radio Service Timeout",
    detail="Radio station search timed out. Please try again.",
    log_level="warning",
)

radio_browser_connection_handler = _make_domain_handler(
    status_code=503,
    error_type="service_unavailable",
    title="Radio Service Unavailable",
    detail="Radio station search is temporarily unavailable. Please try again later.",
    log_level="warning",
)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions."""
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            type="server_error",
            title="Internal Server Error",
            status=500,
            detail="An unexpected error occurred. Please try again later.",
            instance=str(request.url.path),
            code=error_codes.INTERNAL_ERROR,
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# New unified domain handlers
# ---------------------------------------------------------------------------


async def domain_validation_error_handler(
    request: Request, exc: DomainValidationError
) -> JSONResponse:
    """Handle DomainValidationError as 400 with an optional field attribution."""
    logger.warning("Validation Error: %s", exc)
    code = exc.code or error_codes.VALIDATION_ERROR
    errors = None
    if exc.field:
        errors = [
            ErrorItem(
                field=exc.field,
                path=exc.field,
                message=str(exc),
                type="domain_validation_error",
                code=code,
            )
        ]
    return JSONResponse(
        status_code=400,
        content=ErrorDetail(
            type="bad_request",
            title="Validation Error",
            status=400,
            detail=str(exc),
            instance=str(request.url.path),
            errors=errors,
            code=code,
        ).model_dump(),
    )


radio_timeout_handler = _make_domain_handler(
    status_code=504,
    error_type="gateway_timeout",
    title="Radio Service Timeout",
    detail="Radio station search timed out. Please try again.",
    log_level="warning",
)

radio_connection_handler = _make_domain_handler(
    status_code=503,
    error_type="service_unavailable",
    title="Radio Service Unavailable",
    detail="Radio station search is temporarily unavailable. Please try again later.",
    log_level="warning",
)

radio_error_handler = _make_domain_handler(
    status_code=500,
    error_type="server_error",
    title="Radio Service Error",
    exc_info=True,
)

ssh_connection_error_handler = _make_domain_handler(
    status_code=503,
    error_type="service_unavailable",
    title="SSH Connection Failed",
    log_level="warning",
)

ssh_error_handler = _make_domain_handler(
    status_code=500,
    error_type="server_error",
    title="SSH Operation Failed",
    exc_info=True,
)

external_service_error_handler = _make_domain_handler(
    status_code=502,
    error_type="bad_gateway",
    title="External Service Error",
    exc_info=True,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain and HTTP exception handlers on the FastAPI app.

    Order matters: more specific exceptions MUST come before their base classes.
    FastAPI matches the first registered handler whose exception type matches.
    """
    # HTTP layer
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]

    # Domain exceptions (specific → general)
    app.add_exception_handler(DeviceNotFoundError, device_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DeviceConnectionError, device_connection_error_handler)
    app.add_exception_handler(DiscoveryError, discovery_error_handler)
    app.add_exception_handler(DomainValidationError, domain_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(CodedApiError, coded_api_error_handler)  # type: ignore[arg-type]

    # Radio exceptions (unified hierarchy)
    app.add_exception_handler(RadioTimeoutError, radio_timeout_handler)
    app.add_exception_handler(RadioConnectionError, radio_connection_handler)
    app.add_exception_handler(RadioError, radio_error_handler)

    # Legacy radio exceptions (until providers are migrated)
    app.add_exception_handler(RadioBrowserTimeoutError, radio_browser_timeout_handler)
    app.add_exception_handler(
        RadioBrowserConnectionError, radio_browser_connection_handler
    )
    app.add_exception_handler(RadioBrowserError, radio_browser_connection_handler)

    # SSH exceptions
    app.add_exception_handler(SSHConnectionError, ssh_connection_error_handler)
    app.add_exception_handler(SSHError, ssh_error_handler)

    # External services
    app.add_exception_handler(ExternalServiceError, external_service_error_handler)

    # Base domain + catch-all (MUST be last)
    app.add_exception_handler(OpenCloudTouchError, oct_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
