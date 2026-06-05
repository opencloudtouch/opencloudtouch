"""SPA static file serving for FastAPI.

Extracted from main.py (STORY-303) to separate infrastructure concern.
Single Responsibility: Mount frontend assets and register SPA 404 handler.
"""

import logging
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from opencloudtouch.core.exceptions import ErrorDetail

logger = logging.getLogger(__name__)

# API route prefixes — 404 on these returns JSON (not index.html)
_API_PREFIXES = (
    "/api/",
    "/v1/",
    "/bmx/",
    "/core02/",
    "/health",
    "/openapi",
    "/docs",
    "/redoc",
    "/streaming/",
    "/stations/",
    "/device/",
    "/descriptor/",
    "/playlist/",
)


def _is_api_path(path: str) -> bool:
    """Return True if *path* belongs to an API route (must not fall through to SPA)."""
    return any(path.startswith(prefix) for prefix in _API_PREFIXES)


def find_frontend_static_dir(anchor: Path) -> Path:
    """Locate the frontend dist directory relative to *anchor* (typically ``__file__``).

    Checks two locations:
    - Development: four parents up then ``frontend/dist``
    - Production/Docker: two parents up then ``frontend/dist``
    """
    dev_path = anchor.parent.parent.parent.parent / "frontend" / "dist"
    if dev_path.exists():
        return dev_path
    return anchor.parent.parent / "frontend" / "dist"


def _build_api_404_response(path: str, exc) -> JSONResponse:
    """Build a JSON 404 response for API routes."""
    exc_detail = getattr(exc, "detail", None)
    detail = (
        str(exc_detail)
        if exc_detail and exc_detail != "Not Found"
        else f"The requested resource {path} was not found"
    )
    return JSONResponse(
        status_code=404,
        content=ErrorDetail(
            type="not_found",
            title="Not Found",
            status=404,
            detail=detail,
            instance=path,
        ).model_dump(),
    )


def _serve_static_file(static_dir: Path, decoded_path: str) -> FileResponse | None:
    """Try to serve a static file from *static_dir*. Returns None if not found."""
    try:
        requested_path = (static_dir / decoded_path).resolve()
        if str(requested_path).startswith(str(static_dir)) and requested_path.is_file():
            headers = {}
            # Never cache index.html or CSV files — deploys must take effect immediately
            if requested_path.name in ("index.html", "supporters.csv"):
                # Aggressive cache prevention (HTTP/1.1 + HTTP/1.0 + proxies)
                headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate, max-age=0"
                )
                headers["Pragma"] = "no-cache"  # HTTP/1.0 fallback
                headers["Expires"] = "0"  # Proxies
            return FileResponse(requested_path, headers=headers)
    except (ValueError, OSError):
        pass  # Invalid path or I/O error — fall through to 404
    return None


def mount_static_files(app: FastAPI, static_dir: Path) -> None:
    """Mount frontend static files and register SPA 404 handler.

    No-op if *static_dir* does not exist (e.g. backend-only deployments).
    """
    if not static_dir.exists():
        logger.debug(
            "Frontend dist directory not found — skipping static mount (%s)", static_dir
        )
        return

    # Serve static assets (CSS, JS, images) — filenames are content-hashed by Vite,
    # so they can be cached aggressively (new build = new filename = cache miss).
    app.mount(
        "/assets",
        StaticFiles(directory=str(static_dir / "assets")),
        name="assets",
    )

    @app.middleware("http")
    async def _asset_cache_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    # Capture in a local variable so the closure is stable
    _static_dir = static_dir.resolve()

    @app.exception_handler(404)
    async def spa_404_handler(request: Request, exc):
        """Serve index.html for 404s on non-API routes (SPA support).

        - API routes → JSON 404 (machine-readable)
        - Path traversal → 404 (security)
        - Existing file in dist/ → FileResponse
        - Everything else → index.html (React Router handles routing)
        """
        path = request.url.path

        if _is_api_path(path):
            return _build_api_404_response(path, exc)

        # SECURITY: Prevent path traversal (percent-encoded ../ or \)
        decoded_path = unquote(path.lstrip("/"))
        if ".." in decoded_path or "\\" in decoded_path:
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        # Serve actual file if it exists inside dist/
        file_response = _serve_static_file(_static_dir, decoded_path)
        if file_response is not None:
            return file_response

        # Fallback: SPA entry point — never cache so deploys take effect immediately
        return FileResponse(
            _static_dir / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    logger.info("Frontend static files mounted from %s", static_dir)
