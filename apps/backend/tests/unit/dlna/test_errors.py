"""Tests for DLNA error classification."""

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.errors import classify


def test_classify_maps_codes():
    assert classify(LookupError("x"))[:2] == (404, "dlna_server_not_found")
    assert classify(DlnaTimeoutError("x"))[:2] == (504, "dlna_server_timeout")
    assert classify(DlnaBrowseError("x", error_code="701"))[:2] == (
        404,
        "dlna_object_not_found",
    )
    assert classify(DlnaBrowseError("x"))[:2] == (502, "dlna_upstream_error")
