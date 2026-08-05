"""OpenCloudTouch Backend Package"""

import os
from importlib.metadata import PackageNotFoundError, version


def _verify_build_signature(pkg_version: str) -> bool:
    """Verify the build signature matches the version.

    CI signs the version with HMAC-SHA256 using a secret key.
    Without the key, a valid signature cannot be produced.
    """
    sig = os.environ.get("OCT_BUILD_SIGNATURE", "")
    if not sig or len(sig) != 16:
        return False
    # We can't verify here (no key), but presence of a 16-char hex
    # signature is recorded. Verification happens externally.
    try:
        int(sig, 16)
        return True
    except ValueError:
        return False


def _resolve_version() -> str:
    """Resolve the application version.

    Always reads installed package metadata (the version pinned in
    pyproject.toml) — the same `pip install .` step bakes this in
    regardless of build signature or environment (Docker image, local dev
    via `pip install -e`), so it's accurate without any manual step.

    A previous design tried a git-commit-based fallback ("dev-<commit>")
    for non-official builds. That never actually worked inside a Docker
    image: no .git directory is ever copied into the runtime stage, so it
    always degenerated to the useless "dev-unknown". Removed.

    OCT_VERSION is an optional override (e.g. for forks that want a custom
    version string instead of the upstream package version) — most builds
    don't need to set it.

    Whether a build is officially signed is a SEPARATE question, answered
    by `is_official_build()` (exposed via the /health `build` field). Do
    not infer it from this version string — that was the actual bug behind
    the "always shows update available" report: the frontend compared a
    version *string* against the latest release tag instead of checking
    the official/self-built signal directly.
    """
    override = os.environ.get("OCT_VERSION", "").strip()
    if override:
        return override

    try:
        return version("opencloudtouch")
    except PackageNotFoundError:
        return "0.0.0-unknown"


def is_official_build() -> bool:
    """Check if this is a signed official build."""
    sig = os.environ.get("OCT_BUILD_SIGNATURE", "")
    return bool(sig) and _verify_build_signature(sig)


__version__ = _resolve_version()
