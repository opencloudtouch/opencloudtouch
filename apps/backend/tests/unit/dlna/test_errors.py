"""Mapping of DLNA failures to coded REST/press responses."""

import pytest

from opencloudtouch.core import error_codes
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.errors import classify
from opencloudtouch.dlna.service import DlnaNotPlayableError

CASES = [
    (LookupError("x"), (404, error_codes.DLNA_SERVER_NOT_FOUND), 503),
    (DlnaTimeoutError("x"), (504, error_codes.DLNA_SERVER_TIMEOUT), 503),
    (
        DlnaBrowseError("x", error_code="701"),
        (404, error_codes.DLNA_OBJECT_NOT_FOUND),
        404,
    ),
    (DlnaBrowseError("x"), (502, error_codes.DLNA_UPSTREAM_ERROR), 503),
    (DlnaNotPlayableError("x"), (422, error_codes.DLNA_NOT_PLAYABLE), 404),
]


@pytest.mark.parametrize(("exc", "save", "press"), CASES)
def test_classify(exc, save, press):
    status, code, detail = classify(exc)
    assert (status, code) == save
    p_status, p_code, p_detail = classify(exc, press=True)
    assert (p_status, p_code) == (press, save[1])
    assert detail == p_detail
