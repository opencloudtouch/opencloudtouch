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
