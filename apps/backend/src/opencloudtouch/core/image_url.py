"""Heuristic check whether a URL points to an image."""

from urllib.parse import urlparse

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"}


def is_image_url(url: str) -> bool:
    """Heuristic check whether a URL likely points to an image."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower().rstrip("/")

    # A web page is never a logo, even if its path looks like one
    if path_lower.endswith((".html", ".htm")):
        return False

    # Check file extension
    for ext in _IMAGE_EXTENSIONS:
        if path_lower.endswith(ext):
            return True

    # Known image CDN patterns
    host = parsed.hostname or ""
    if any(
        pattern in host
        for pattern in ("cdn-profiles.tunein.com", "cdn-radiotime", "cloudfront.net")
    ):
        return True

    # URL path contains a typical image path segment (whole segment, not a prefix)
    segments = set(path_lower.split("/"))
    if segments & {"images", "img", "logo", "favicon", "icon"}:
        return True

    return False
