"""Mapping of DLNA failures to stable error codes and HTTP statuses."""

from opencloudtouch.core import error_codes
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.service import DlnaNotPlayableError


def classify(
    exc: LookupError | DlnaBrowseError | DlnaNotPlayableError, *, press: bool = False
) -> tuple[int, str, str]:
    """Map a DLNA failure to (status, code, fixed detail).

    ``press`` selects the statuses of the Orion call (the speaker is the caller): 503
    for server problems, 404 for object problems. Details never carry URLs or titles.
    """
    if isinstance(exc, LookupError):
        return (
            503 if press else 404,
            error_codes.DLNA_SERVER_NOT_FOUND,
            "DLNA server not found",
        )
    if isinstance(exc, DlnaTimeoutError):
        return (
            503 if press else 504,
            error_codes.DLNA_SERVER_TIMEOUT,
            "DLNA server did not answer in time",
        )
    if isinstance(exc, DlnaNotPlayableError):
        return (
            404 if press else 422,
            error_codes.DLNA_NOT_PLAYABLE,
            "DLNA object is not playable",
        )
    if exc.error_code == "701":
        return 404, error_codes.DLNA_OBJECT_NOT_FOUND, "DLNA object not found"
    return (
        503 if press else 502,
        error_codes.DLNA_UPSTREAM_ERROR,
        "DLNA server request failed",
    )
