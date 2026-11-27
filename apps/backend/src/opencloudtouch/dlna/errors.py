"""Map DLNA browse failures to public coded API errors."""

from opencloudtouch.core import error_codes
from opencloudtouch.dlna.client import (
    DlnaBrowseError,
    DlnaSearchUnsupportedError,
    DlnaTimeoutError,
)


def classify(exc: Exception) -> tuple[int, str, str]:
    """Return (status, code, fixed detail); never echoes URLs or titles."""
    if isinstance(exc, LookupError):
        return 404, error_codes.DLNA_SERVER_NOT_FOUND, "Media server not found"
    if isinstance(exc, DlnaTimeoutError):
        return 504, error_codes.DLNA_SERVER_TIMEOUT, "Media server timed out"
    if isinstance(exc, DlnaSearchUnsupportedError):
        return 409, error_codes.DLNA_SEARCH_UNSUPPORTED, "Media server cannot search"
    # 710: unknown search container.
    if isinstance(exc, DlnaBrowseError) and exc.error_code in ("701", "710"):
        return 404, error_codes.DLNA_OBJECT_NOT_FOUND, "Object not found"
    return 502, error_codes.DLNA_UPSTREAM_ERROR, "Media server request failed"
