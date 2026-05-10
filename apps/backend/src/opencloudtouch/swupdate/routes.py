"""SWUpdate routes for SoundTouch firmware index emulation.

Emulates the firmware update endpoints normally served by worldwide.bose.com.
The device's SoundTouchSdkPrivateCfg.xml redirects firmware checks to OCT via:
  <swUpdateUrl>http://content.api.bose.io:7777/updates/soundtouch</swUpdateUrl>

Endpoints:
  GET /updates/soundtouch          → Firmware INDEX.XML (real Bose format)
  GET /ced/eup/downloads/rel/{file} → Blocked (prevents unintended updates)
  GET /ced/soundtouch/downloads_stockholm/... → Blocked
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["swupdate"])

_MEDIA_XML = "application/xml"
_INDEX_XML_PATH = Path(__file__).parent / "firmware_index.xml"
_INDEX_XML: str | None = None


def _load_index_xml() -> str:
    """Load the static firmware index XML (cached after first read)."""
    global _INDEX_XML
    if _INDEX_XML is None:
        logger.debug("Loading firmware index from %s", _INDEX_XML_PATH)
        _INDEX_XML = _INDEX_XML_PATH.read_text(encoding="utf-8")
        logger.debug("Firmware index loaded: %d bytes", len(_INDEX_XML))
    return _INDEX_XML


@router.get("/updates/soundtouch")
async def firmware_index():
    """Return firmware INDEX.XML for SoundTouch devices.

    Serves the original Bose worldwide.bose.com index so devices recognise
    their current firmware as up-to-date and don't attempt downloads.
    """
    logger.info("[swupdate] Firmware index requested")
    xml = _load_index_xml()
    return Response(content=xml, media_type=_MEDIA_XML)


@router.get("/ced/eup/downloads/rel/{filename:path}")
async def firmware_download_legacy(filename: str):
    """Block legacy firmware download path."""
    logger.warning("[swupdate] Firmware download requested (legacy) — blocked")
    return Response(
        content="<error>Firmware downloads disabled by OCT</error>",
        media_type=_MEDIA_XML,
        status_code=404,
    )


@router.get("/ced/soundtouch/downloads_stockholm/{path:path}")
async def firmware_download(path: str):
    """Block real Bose firmware download path.

    The real index XML references https://downloads.bose.com/ced/soundtouch/...
    but since swUpdateUrl points to OCT, the device may try to fetch from here.
    We return 404 to prevent unintended firmware updates.
    """
    logger.warning("[swupdate] Firmware download requested — blocked")
    return Response(
        content="<error>Firmware downloads disabled by OCT</error>",
        media_type=_MEDIA_XML,
        status_code=404,
    )
