"""Legacy BMX Resolve Endpoint.

Extracted from bmx/routes.py (STORY-306): POST /bmx/resolve and its
XML helper functions live here to keep bmx/routes.py under 200 lines.
"""

import logging
import os
import re
from xml.etree.ElementTree import Element
from xml.sax.saxutils import escape as xml_escape

from defusedxml.ElementTree import fromstring as parse_xml_string
from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

resolve_router = APIRouter(tags=["bmx"])


# =============================================================================
# Helper functions
# =============================================================================


def _get_elem_text(elem: Element | None, default: str) -> str:
    """Return element text or default if element is None."""
    return (elem.text or default) if elem is not None else default


def _build_oct_resolved_xml(
    location: str, item_name: str, station_name: str
) -> str | None:
    """Build resolved ContentItem XML for OCT-relative preset locations.

    Args:
        location: OCT path like /oct/device/{id}/preset/{N}
        item_name: Station item name
        station_name: Station display name

    Returns:
        Resolved XML string, or None if location does not match expected format.
    """
    match = re.match(r"/oct/device/([^/]+)/preset/(\d+)", location)
    if not match:
        logger.debug(
            "[BMX RESOLVE] Location '%s' does not match OCT preset pattern", location
        )
        return None

    device_id = match.group(1)
    preset_number = match.group(2)
    oct_url = os.getenv(
        "OCT_BACKEND_URL", "http://content.api.bose.io:7777"
    )  # NOSONAR — Bose devices use HTTP
    resolved_url = f"{oct_url}/device/{device_id}/preset/{preset_number}"

    logger.info("[BMX RESOLVE] OCT location resolved: %s → %s", location, resolved_url)
    logger.debug(
        "[BMX RESOLVE] Resolved details: device=%s, preset=%s, item=%s, station=%s",
        device_id,
        preset_number,
        item_name,
        station_name,
    )
    return (
        f'<ContentItem source="INTERNET_RADIO" type="stationurl"'
        f' location="{resolved_url}" isPresetable="true">\n'
        f"  <itemName>{xml_escape(item_name)}</itemName>\n"
        f"  <stationName>{xml_escape(station_name)}</stationName>\n"
        f"</ContentItem>"
    )


def _is_pass_through(source: str, location: str, station_id: str) -> bool:
    """Return True if the ContentItem should be forwarded as-is to the device."""
    if location.startswith("http://") or location.startswith("https://"):
        logger.info("[BMX RESOLVE] Direct URL or OCT proxy - pass through")
        return True
    if source == "TUNEIN" and station_id:
        logger.warning("[BMX RESOLVE] TuneIn station %s not supported yet", station_id)
        return True
    if source and source not in ("INTERNET_RADIO", "TUNEIN"):
        logger.info("[BMX RESOLVE] %s source - pass through", source)
        return True
    return False


# =============================================================================
# Route handler
# =============================================================================


@resolve_router.post("/bmx/resolve")
async def resolve_stream(request: Request) -> Response:
    """Resolve ContentItem to playable stream URL.

    Bose devices call this endpoint with a ContentItem XML to resolve:
    - TuneIn station IDs → direct stream URLs
    - Direct stream URLs → pass through
    - OCT stream proxy URLs → pass through

    This mimics the original Bose BMX server (bmx.bose.com).
    """
    try:
        body_str = (await request.body()).decode("utf-8")
        logger.info("[BMX RESOLVE] Request body: %s", body_str)

        root = parse_xml_string(body_str)
        source = root.get("source", "")
        location = root.get("location", "")
        station_id = root.get("stationId", "")
        item_name_text = _get_elem_text(root.find("itemName"), "Unknown")
        station_name_text = _get_elem_text(root.find("stationName"), item_name_text)

        logger.info(
            "[BMX RESOLVE] source=%s, location=%s, stationId=%s",
            source,
            location,
            station_id,
        )

        if location and location.startswith("/oct/device/"):
            resolved_xml = _build_oct_resolved_xml(
                location, item_name_text, station_name_text
            )
            if resolved_xml:
                return Response(content=resolved_xml, media_type="application/xml")

        if _is_pass_through(source, location, station_id):
            return Response(content=body_str, media_type="application/xml")

        logger.error("[BMX RESOLVE] Unable to resolve stream")
        return Response(
            content="<error>Unable to resolve stream</error>",
            status_code=400,
            media_type="application/xml",
        )

    except Exception:
        logger.exception("[BMX RESOLVE] Error")
        return Response(
            content="<error>Resolution failed</error>",
            status_code=500,
            media_type="application/xml",
        )
