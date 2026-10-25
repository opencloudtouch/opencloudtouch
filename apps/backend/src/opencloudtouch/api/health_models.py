"""Response model of the ``/health`` endpoint (part of the OpenAPI contract)."""

from typing import Literal

from pydantic import BaseModel


class HealthConfig(BaseModel):
    """Configuration flags exposed by ``/health``."""

    discovery_enabled: bool


class HealthResponse(BaseModel):
    """Minimal health payload for Docker health checks and the About page."""

    status: str
    service: str
    version: str
    build: Literal["official", "community"]
    uptime: int
    config: HealthConfig
