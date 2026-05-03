"""Shared stream URL utilities for BMX modules."""

import logging

logger = logging.getLogger(__name__)


def convert_https_to_http(url: str) -> str:
    """Convert HTTPS URLs to HTTP for Bose device compatibility.

    Bose SoundTouch devices cannot play HTTPS streams directly.
    Most radio stations support both HTTP and HTTPS, so we try HTTP first.

    Args:
        url: Stream URL (may be HTTPS or HTTP)

    Returns:
        HTTP version of the URL (https:// → http://)
    """
    if url.startswith("https://"):
        http_url = "http://" + url[8:]  # NOSONAR - intentional HTTP for Bose SoundTouch
        logger.info(
            f"[BMX] Converting HTTPS to HTTP: {url[:50]}... → {http_url[:50]}..."
        )
        return http_url
    return url
