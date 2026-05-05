"""
Radio API Endpoints

Provides REST API for searching and retrieving radio stations.
"""

import os
from enum import Enum
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from opencloudtouch.radio.adapter import get_radio_adapter
from opencloudtouch.radio.models import RadioStation
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
)
from opencloudtouch.radio.providers.tunein import (
    TuneInConnectionError,
    TuneInError,
    TuneInTimeoutError,
)

# Router
router = APIRouter(prefix="/api/radio", tags=["radio"])


# Request/Response Models
class RadioStationResponse(BaseModel):
    """Radio station response model (unified across all providers)."""

    uuid: str  # Mapped from station_id for API compatibility
    name: str
    url: str
    homepage: str | None = None
    favicon: str | None = None
    tags: list[str] | None = None
    country: str
    codec: str | None = None
    bitrate: int | None = None
    provider: str = "unknown"

    @classmethod
    def from_station(cls, station: RadioStation) -> "RadioStationResponse":
        """Convert RadioStation to response model."""
        return cls(
            uuid=station.station_id,
            name=station.name,
            url=station.url,
            homepage=station.homepage,
            favicon=station.favicon,
            tags=station.tags,
            country=station.country,
            codec=station.codec,
            bitrate=station.bitrate,
            provider=station.provider,
        )


class RadioSearchResponse(BaseModel):
    """Search results response."""

    stations: List[RadioStationResponse]


class SearchType(str, Enum):
    """Search type enum."""

    NAME = "name"
    COUNTRY = "country"
    TAG = "tag"


class ProviderType(str, Enum):
    """Radio provider enum."""

    RADIOBROWSER = "radiobrowser"
    TUNEIN = "tunein"


# Endpoints
@router.get("/search", response_model=RadioSearchResponse)
async def search_stations(
    q: str = Query(..., min_length=1, description="Search query"),
    search_type: SearchType = Query(
        SearchType.NAME, description="Search type: name, country, or tag"
    ),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    provider: ProviderType = Query(
        ProviderType.RADIOBROWSER, description="Radio provider: radiobrowser or tunein"
    ),
):
    """
    Search radio stations.

    - **q**: Search query (required, min 1 character)
    - **search_type**: Type of search - name, country, or tag (default: name)
    - **limit**: Maximum results (1-100, default: 10)
    - **provider**: Radio provider - radiobrowser or tunein (default: radiobrowser)
    """
    # Guard: reject tunein when extended resolver is disabled
    if (
        provider == ProviderType.TUNEIN
        and os.getenv("OCT_EXTENDED_RESOLVER", "true").lower() != "true"
    ):
        raise HTTPException(
            status_code=400,
            detail="Provider 'tunein' is not available",
        )

    adapter = get_radio_adapter(provider.value)

    try:
        # Route to appropriate search method
        if search_type == SearchType.NAME:
            stations = await adapter.search_by_name(q, limit=limit)
        elif search_type == SearchType.COUNTRY:
            stations = await adapter.search_by_country(q, limit=limit)
        elif search_type == SearchType.TAG:
            stations = await adapter.search_by_tag(q, limit=limit)
        else:  # pragma: no cover
            raise HTTPException(  # pragma: no cover
                status_code=422, detail=f"Invalid search type: {search_type}"
            )

        # Convert to response model
        return RadioSearchResponse(
            stations=[RadioStationResponse.from_station(s) for s in stations]
        )

    except (RadioBrowserTimeoutError, TuneInTimeoutError) as e:
        raise HTTPException(status_code=504, detail=f"Radio API timeout: {e}") from e
    except (RadioBrowserConnectionError, TuneInConnectionError) as e:
        raise HTTPException(
            status_code=503, detail=f"Cannot connect to radio API: {e}"
        ) from e
    except (RadioBrowserError, TuneInError) as e:
        raise HTTPException(status_code=500, detail=f"Radio API error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e


@router.get("/station/{uuid}", response_model=RadioStationResponse)
async def get_station_detail(
    uuid: str,
    provider: ProviderType = Query(
        ProviderType.RADIOBROWSER, description="Radio provider: radiobrowser or tunein"
    ),
):
    """
    Get radio station detail by UUID.

    - **uuid**: Station UUID
    - **provider**: Radio provider - radiobrowser or tunein (default: radiobrowser)
    """
    adapter = get_radio_adapter(provider.value)

    try:
        station = await adapter.get_station_by_uuid(uuid)
        return RadioStationResponse.from_station(station)

    except (RadioBrowserTimeoutError, TuneInTimeoutError) as e:
        raise HTTPException(status_code=504, detail=f"Radio API timeout: {e}") from e
    except (RadioBrowserConnectionError, TuneInConnectionError) as e:
        raise HTTPException(
            status_code=503, detail=f"Cannot connect to radio API: {e}"
        ) from e
    except (RadioBrowserError, TuneInError) as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404, detail=f"Station not found: {uuid}"
            ) from e
        raise HTTPException(status_code=500, detail=f"Radio API error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}") from e
