"""Heuristic check whether a URL points to an image."""

from urllib.parse import urlparse

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"}


def is_image_url(url: str) -> bool:
    """Heuristic check whether a URL likely points to an image."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower().rstrip("/")

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

    # URL path contains typical image path segments
    if any(
        seg in path_lower for seg in ("/images/", "/img/", "/logo", "/favicon", "/icon")
    ):
        return True

    return False
