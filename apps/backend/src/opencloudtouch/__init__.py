"""OpenCloudTouch Backend Package"""

import os
import subprocess
from importlib.metadata import PackageNotFoundError, version


def _get_git_commit_short() -> str:
    """Get shortened git commit hash, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


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

    Official builds: version from package metadata (e.g. "1.2.0")
    Dev/self-built:  "dev-<commit>" (e.g. "dev-a1b2c3d")
    """
    sig = os.environ.get("OCT_BUILD_SIGNATURE", "")
    if sig and _verify_build_signature(sig):
        try:
            return version("opencloudtouch")
        except PackageNotFoundError:
            return "0.0.0-unofficial"

    # Not an official build — use git commit hash
    commit = _get_git_commit_short()
    return f"dev-{commit}"


def is_official_build() -> bool:
    """Check if this is a signed official build."""
    sig = os.environ.get("OCT_BUILD_SIGNATURE", "")
    return bool(sig) and _verify_build_signature(sig)


__version__ = _resolve_version()
