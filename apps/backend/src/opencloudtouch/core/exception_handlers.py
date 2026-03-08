"""
RFC 7807-inspired standardized exception handlers for OpenCloudTouch.

All domain and HTTP exceptions are mapped to a consistent ErrorDetail response
format. Register them all via ``register_exception_handlers(app)``.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DiscoveryError,
    ErrorDetail,
    OpenCloudTouchError,
    map_status_to_type,
)
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
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
            errors=[
                {
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                }
                for err in exc.errors()
            ],
        ).model_dump(),
    )


async def device_not_found_handler(
    request: Request, exc: DeviceNotFoundError
) -> JSONResponse:
    """Handle DeviceNotFoundError as 404 HTTP response."""
    logger = logging.getLogger(__name__)
    logger.warning(f"Device not found: {exc.device_id}")
    return JSONResponse(
        status_code=404,
        content=ErrorDetail(
            type="not_found",
            title="Device Not Found",
            status=404,
            detail=str(exc),
            instance=str(request.url.path),
        ).model_dump(),
    )


async def device_connection_error_handler(
    request: Request, exc: DeviceConnectionError
) -> JSONResponse:
    """Handle DeviceConnectionError as 503 Service Unavailable."""
    logger = logging.getLogger(__name__)
    logger.error(f"Device connection failed: {exc.device_ip}", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content=ErrorDetail(
            type="service_unavailable",
            title="Device Unavailable",
            status=503,
            detail=str(exc),
            instance=str(request.url.path),
        ).model_dump(),
    )


async def discovery_error_handler(
    request: Request, exc: DiscoveryError
) -> JSONResponse:
    """Handle DiscoveryError as 500 Internal Server Error."""
    logger = logging.getLogger(__name__)
    logger.error(f"Discovery failed: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            type="server_error",
            title="Device Discovery Failed",
            status=500,
            detail=str(exc),
            instance=str(request.url.path),
        ).model_dump(),
    )


async def oct_error_handler(request: Request, exc: OpenCloudTouchError) -> JSONResponse:
    """Catch-all for other OpenCloudTouch domain exceptions."""
    logger = logging.getLogger(__name__)
    logger.error(f"OpenCloudTouch error: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            type="server_error",
            title="Internal Error",
            status=500,
            detail=str(exc),
            instance=str(request.url.path),
        ).model_dump(),
    )


async def radio_browser_timeout_handler(
    request: Request, exc: RadioBrowserTimeoutError
) -> JSONResponse:
    """Handle RadioBrowserTimeoutError as 504 Gateway Timeout."""
    logger = logging.getLogger(__name__)
    logger.warning(f"Radio browser timeout: {exc}")
    return JSONResponse(
        status_code=504,
        content=ErrorDetail(
            type="gateway_timeout",
            title="Radio Service Timeout",
            status=504,
            detail="Radio station search timed out. Please try again.",
            instance=str(request.url.path),
        ).model_dump(),
    )


async def radio_browser_connection_handler(
    request: Request, exc: RadioBrowserError
) -> JSONResponse:
    """Handle RadioBrowserConnectionError and RadioBrowserError as 503 Service Unavailable."""
    logger = logging.getLogger(__name__)
    logger.warning(f"Radio browser unavailable: {exc}")
    return JSONResponse(
        status_code=503,
        content=ErrorDetail(
            type="service_unavailable",
            title="Radio Service Unavailable",
            status=503,
            detail="Radio station search is temporarily unavailable. Please try again later.",
            instance=str(request.url.path),
        ).model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions."""
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            type="server_error",
            title="Internal Server Error",
            status=500,
            detail=str(exc),
            instance=str(request.url.path),
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain and HTTP exception handlers on the FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(DeviceNotFoundError, device_not_found_handler)
    app.add_exception_handler(DeviceConnectionError, device_connection_error_handler)
    app.add_exception_handler(DiscoveryError, discovery_error_handler)
    app.add_exception_handler(OpenCloudTouchError, oct_error_handler)
    app.add_exception_handler(RadioBrowserTimeoutError, radio_browser_timeout_handler)
    app.add_exception_handler(
        RadioBrowserConnectionError, radio_browser_connection_handler
    )
    app.add_exception_handler(RadioBrowserError, radio_browser_connection_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
