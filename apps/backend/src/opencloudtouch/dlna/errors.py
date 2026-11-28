"""Map DLNA browse failures to public coded API errors."""

from opencloudtouch.core import error_codes
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError


def classify(exc: Exception) -> tuple[int, str, str]:
    """Return (status, code, fixed detail); never echoes URLs or titles."""
    if isinstance(exc, LookupError):
        return 404, error_codes.DLNA_SERVER_NOT_FOUND, "Media server not found"
    if isinstance(exc, DlnaTimeoutError):
        return 504, error_codes.DLNA_SERVER_TIMEOUT, "Media server timed out"
    if isinstance(exc, DlnaBrowseError) and exc.error_code == "701":
        return 404, error_codes.DLNA_OBJECT_NOT_FOUND, "Object not found"
    return 502, error_codes.DLNA_UPSTREAM_ERROR, "Media server request failed"
