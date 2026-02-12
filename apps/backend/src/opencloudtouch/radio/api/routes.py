"""
Radio API Endpoints

Provides REST API for searching and retrieving radio stations.
"""

from enum import Enum
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from opencloudtouch.radio.adapter import get_radio_adapter
from opencloudtouch.radio.provider import RadioProvider
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
    RadioStation,
)

# Router
router = APIRouter(prefix="/api/radio", tags=["radio"])


# Request/Response Models
class RadioStationResponse(BaseModel):
    """Radio station response model."""

    uuid: str
    name: str
    url: str
    url_resolved: str | None = None
    homepage: str | None = None
    favicon: str | None = None
    tags: str | None = None
    country: str
    countrycode: str | None = None
    state: str | None = None
    language: str | None = None
    languagecodes: str | None = None
    votes: int | None = None
    codec: str
    bitrate: int | None = None
    hls: bool | None = None
    lastcheckok: bool | None = None
    clickcount: int | None = None
    clicktrend: int | None = None

    @classmethod
    def from_station(cls, station: RadioStation) -> "RadioStationResponse":
        """Convert RadioStation to response model."""
        return cls(
            uuid=station.station_uuid,
            name=station.name,
            url=station.url,
            url_resolved=station.url_resolved,
            homepage=station.homepage,
            favicon=station.favicon,
            tags=station.tags,
            country=station.country,
            countrycode=station.countrycode,
            state=station.state,
            language=station.language,
            languagecodes=station.languagecodes,
            votes=station.votes,
            codec=station.codec,
            bitrate=station.bitrate,
            hls=station.hls,
            lastcheckok=station.lastcheckok,
            clickcount=station.clickcount,
            clicktrend=station.clicktrend,
        )


class RadioSearchResponse(BaseModel):
    """Search results response."""

    stations: List[RadioStationResponse]


class SearchType(str, Enum):
    """Search type enum."""

    NAME = "name"
    COUNTRY = "country"
    TAG = "tag"


# Dependency Injection
def get_radio_provider() -> RadioProvider:
    """Factory: Get radio provider (Mock or Real based on OCT_MOCK_MODE)."""
    return get_radio_adapter()


# Endpoints
@router.get("/search", response_model=RadioSearchResponse)
async def search_stations(
    q: str = Query(..., min_length=1, description="Search query"),
    search_type: SearchType = Query(
        SearchType.NAME, description="Search type: name, country, or tag"
    ),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    adapter: RadioProvider = Depends(get_radio_provider),
):
    """
    Search radio stations.

    - **q**: Search query (required, min 1 character)
    - **search_type**: Type of search - name, country, or tag (default: name)
    - **limit**: Maximum results (1-100, default: 10)
    """
    try:
        # Route to appropriate search method
        if search_type == SearchType.NAME:
            stations = await adapter.search_by_name(q, limit=limit)
        elif search_type == SearchType.COUNTRY:
            stations = await adapter.search_by_country(q, limit=limit)
        elif search_type == SearchType.TAG:
            stations = await adapter.search_by_tag(q, limit=limit)
        else:
            raise HTTPException(
                status_code=422, detail=f"Invalid search type: {search_type}"
            )

        # Convert to response model
        return RadioSearchResponse(
            stations=[RadioStationResponse.from_station(s) for s in stations]
        )

    except RadioBrowserTimeoutError as e:
        raise HTTPException(
            status_code=504, detail=f"RadioBrowser API timeout: {e}"
        ) from e
    except RadioBrowserConnectionError as e:
        raise HTTPException(
            status_code=503, detail=f"Cannot connect to RadioBrowser API: {e}"
        ) from e
    except RadioBrowserError as e:
        raise HTTPException(
            status_code=500, detail=f"RadioBrowser API error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e


@router.get("/station/{uuid}", response_model=RadioStationResponse)
async def get_station_detail(
    uuid: str, adapter: RadioProvider = Depends(get_radio_provider)
):
    """
    Get radio station detail by UUID.

    - **uuid**: Station UUID
    """
    try:
        station = await adapter.get_station_by_uuid(uuid)
        return RadioStationResponse.from_station(station)

    except RadioBrowserTimeoutError as e:
        raise HTTPException(
            status_code=504, detail=f"RadioBrowser API timeout: {e}"
        ) from e
    except RadioBrowserConnectionError as e:
        raise HTTPException(
            status_code=503, detail=f"Cannot connect to RadioBrowser API: {e}"
        ) from e
    except RadioBrowserError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404, detail=f"Station not found: {uuid}"
            ) from e
        raise HTTPException(
            status_code=500, detail=f"RadioBrowser API error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e
