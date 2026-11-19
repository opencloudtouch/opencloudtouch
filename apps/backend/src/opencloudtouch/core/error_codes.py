"""Registry of machine-readable API error codes.

Codes are public contract: they are never renamed or removed after release
(enforced by ``tests/unit/core/test_error_codes.py``). Format:
``^[a-z][a-z0-9_]*$``, unique across the API, prefixed by domain when
feature-specific (for example ``mqtt_invalid_host``). Feature specs add their
constants here.
"""

import re

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

DEVICE_NOT_FOUND = "device_not_found"
DEVICE_UNREACHABLE = "device_unreachable"
INTERNAL_ERROR = "internal_error"
NOT_FOUND = "not_found"
VALIDATION_ERROR = "validation_error"


def validate_code(code: str) -> str:
    """Return *code* unchanged or raise ``ValueError`` if it violates the code format."""
    if not CODE_PATTERN.match(code):
        raise ValueError(
            f"invalid error code {code!r}: must match {CODE_PATTERN.pattern}"
        )
    return code


# Stereo pairs
STEREO_PAIR_DEVICE_NOT_CAPABLE = "stereo_pair_device_not_capable"
STEREO_PAIR_DEVICE_NOT_PROVISIONED = "stereo_pair_device_not_provisioned"
STEREO_PAIR_DEVICE_IN_ZONE = "stereo_pair_device_in_zone"
STEREO_PAIR_DEVICE_IN_PAIR = "stereo_pair_device_in_pair"
STEREO_PAIR_DEVICE_UNREACHABLE = "stereo_pair_device_unreachable"
STEREO_PAIR_MARGE_FAILED = "stereo_pair_marge_failed"
STEREO_PAIR_VERIFICATION_FAILED = "stereo_pair_verification_failed"
STEREO_PAIR_DEGRADED = "stereo_pair_degraded"
STEREO_PAIR_NOT_FOUND = "stereo_pair_not_found"
STEREO_PAIR_INVALID_REQUEST = "stereo_pair_invalid_request"
STEREO_PAIR_OPERATION_NOT_FOUND = "stereo_pair_operation_not_found"
